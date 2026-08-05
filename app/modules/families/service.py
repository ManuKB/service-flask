import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.family import Family
from app.models.family_membership import FamilyMembership
from app.models.user import User
from app.modules.audit.service import record_event
from app.modules.auth import service as auth_service
from app.modules.notifications import service as notifications_service
from app.modules.permissions.roles import FamilyRole, MembershipStatus

settings = get_settings()


class FamilyError(Exception):
    """Raised for any family-domain failure the router should turn into an HTTP error."""


def create_family(db: Session, owner_user_id: uuid.UUID, name: str) -> Family:
    existing_owned = db.scalar(select(Family).where(Family.owner_user_id == owner_user_id))
    if existing_owned:
        raise FamilyError("User already owns a family")

    owner = db.get(User, owner_user_id)
    if not owner:
        raise FamilyError("Owning user could not be found")

    family = Family(name=name, owner_user_id=owner_user_id)
    db.add(family)
    db.flush()

    db.add(
        FamilyMembership(
            family_id=family.id,
            user_id=owner_user_id,
            role=FamilyRole.OWNER,
            status=MembershipStatus.ACTIVE,
            joined_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    db.refresh(family)

    record_event(
        db,
        family_id=family.id,
        actor_user_id=owner_user_id,
        action="family.created",
        entity_type="Family",
        entity_id=family.id,
        new_value={"name": family.name},
        source_service="families",
    )
    return family


def get_family_for_user(db: Session, user_id: uuid.UUID) -> Family | None:
    """MVP assumption: one active family per user. Returns the first active
    membership's family; extend to a list once multi-family support lands."""
    membership = db.scalar(
        select(FamilyMembership).where(
            FamilyMembership.user_id == user_id,
            FamilyMembership.status == MembershipStatus.ACTIVE,
        )
    )
    if not membership:
        return None
    return db.get(Family, membership.family_id)


def list_members(db: Session, family_id: uuid.UUID) -> list[FamilyMembership]:
    result = db.scalars(select(FamilyMembership).where(FamilyMembership.family_id == family_id))
    return list(result)


def add_member(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    role: FamilyRole,
) -> FamilyMembership:
    """Called directly by the invitations module once an invite is accepted -
    invitations owns the Invitation row, families owns membership."""
    family = db.get(Family, family_id)
    if not family:
        raise FamilyError("Family not found")

    existing = db.scalar(
        select(FamilyMembership).where(
            FamilyMembership.family_id == family_id,
            FamilyMembership.user_id == user_id,
        )
    )
    if existing:
        raise FamilyError("User is already a member of this family")

    membership = FamilyMembership(
        family_id=family_id,
        user_id=user_id,
        role=role,
        status=MembershipStatus.ACTIVE,
        joined_at=datetime.now(timezone.utc),
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=user_id,
        action="invitation.accepted",
        entity_type="FamilyMembership",
        entity_id=membership.id,
        new_value={"role": role.value},
        source_service="families",
    )
    return membership


def change_member_role(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    new_role: FamilyRole,
    actor_user_id: uuid.UUID,
) -> FamilyMembership:
    membership = db.get(FamilyMembership, member_id)
    if not membership or membership.family_id != family_id:
        raise FamilyError("Membership not found")

    old_role = membership.role
    membership.role = new_role
    db.commit()
    db.refresh(membership)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=actor_user_id,
        action="role.changed",
        entity_type="FamilyMembership",
        entity_id=member_id,
        old_value={"role": old_role.value},
        new_value={"role": new_role.value},
        source_service="families",
    )
    return membership


def add_member_by_email(
    db: Session,
    family_id: uuid.UUID,
    owner_user_id: uuid.UUID,
    email: str,
    role: FamilyRole,
    name: str,
) -> tuple[FamilyMembership, bool, str | None]:
    """Owner-initiated add (distinct from the invitations module's
    invite-then-accept flow): the owner supplies the email directly and the
    person is a member immediately - no separate acceptance step.

    * If that email already has an account, they're added right away (they
      already have working credentials).
    * If not, a real User row is created for them with an unusable random
      password (must_set_password=True) and they're emailed a link to set
      their own password on first login - returns created_new_account=True."""
    # Local import: invitations.service imports families.service at module
    # load time (for FamilyError/add_member), so importing it back at this
    # module's top level would be circular - deferring to call time breaks the cycle.
    from app.modules.invitations import service as invitations_service

    family = db.get(Family, family_id)
    if not family:
        raise FamilyError("Family not found")

    existing_user = auth_service.get_user_by_email(db, email)
    created_new_account = existing_user is None
    # A given name is only meaningful for a brand-new account - an existing
    # user already chose their own name at registration, so it's left alone.
    user = existing_user or auth_service.create_user_awaiting_password(db, email, name)

    membership = add_member(db, family_id, user.id, role)

    setup_link: str | None = None
    if created_new_account:
        raw_token = auth_service.issue_password_setup_token(db, user.id)
        setup_link = f"{settings.web_app_base_url}/set-password/{raw_token}"
        invitations_service.get_email_sender().send_password_setup_email(user.email, family.name, setup_link)
    else:
        title = "Added to a family"
        body = f"You were added to {family.name} as {role.value}"
        notification = notifications_service.notify_user(db, family_id, user.id, title, body)
        db.commit()
        db.refresh(notification)

    return membership, created_new_account, setup_link


def to_membership_dict(db: Session, membership: FamilyMembership) -> dict:
    """Enriches a FamilyMembership with its linked User's display name/email
    (MembershipResponse needs user_name/user_email, which don't exist on the
    membership row itself) - kept separate from the CRUD functions above so
    their return types stay plain ORM rows for other callers."""
    user = db.get(User, membership.user_id)
    display_name = (user.name if user else None) or (user.email if user else "Unknown")
    return {
        "id": membership.id,
        "family_id": membership.family_id,
        "user_id": membership.user_id,
        "role": membership.role,
        "status": membership.status,
        "joined_at": membership.joined_at,
        "user_name": display_name,
        "user_email": user.email if user else "",
    }


def to_membership_dicts(db: Session, memberships: list[FamilyMembership]) -> list[dict]:
    return [to_membership_dict(db, membership) for membership in memberships]
