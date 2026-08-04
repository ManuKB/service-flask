import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_token
from app.models.family import Family
from app.models.family_membership import FamilyMembership
from app.models.invitation import Invitation
from app.modules.audit.service import record_event
from app.modules.families.service import FamilyError, add_member
from app.modules.invitations.email import get_email_sender
from app.modules.invitations.statuses import InvitationStatus
from app.modules.permissions.roles import FamilyRole

settings = get_settings()
INVITE_TTL = timedelta(days=7)


class InvitationError(Exception):
    """Raised for any invitation-domain failure the router should turn into an HTTP error."""


def _generate_raw_token() -> str:
    return secrets.token_urlsafe(32)


def create_invitation(
    db: Session,
    family_id: uuid.UUID,
    inviter_user_id: uuid.UUID,
    email: str,
    role: FamilyRole,
) -> Invitation:
    family = db.get(Family, family_id)
    if family is None:
        raise InvitationError("Family not found")

    raw_token = _generate_raw_token()
    expires_at = datetime.now(timezone.utc) + INVITE_TTL

    invitation = Invitation(
        family_id=family_id,
        email=email,
        token_hash=hash_token(raw_token),
        role=role,
        status=InvitationStatus.PENDING,
        invited_by_user_id=inviter_user_id,
        expires_at=expires_at,
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    # Raw token is never returned in the API response - only ever delivered
    # via the email hook, so a leaked API log can't be used to accept an invite.
    invite_link = f"{settings.web_app_base_url}/invitations/{raw_token}"
    get_email_sender().send_invitation_email(email, family.name, invite_link)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=inviter_user_id,
        action="invitation.created",
        entity_type="Invitation",
        entity_id=invitation.id,
        new_value={"email": email, "role": role.value},
        source_service="invitations",
    )
    return invitation


def _get_valid_invitation(db: Session, raw_token: str) -> Invitation:
    token_hash = hash_token(raw_token)
    invitation = db.scalar(select(Invitation).where(Invitation.token_hash == token_hash))
    if not invitation:
        raise InvitationError("Invitation not found")
    if invitation.status != InvitationStatus.PENDING:
        raise InvitationError("Invitation has already been used")
    # SQLite doesn't persist tzinfo, so a value read back can be naive even
    # though it was written as UTC - normalize before comparing.
    expires_at = (
        invitation.expires_at.replace(tzinfo=timezone.utc)
        if invitation.expires_at.tzinfo is None
        else invitation.expires_at
    )
    if expires_at < datetime.now(timezone.utc):
        invitation.status = InvitationStatus.EXPIRED
        db.commit()
        raise InvitationError("Invitation has expired")
    return invitation


def preview_invitation(db: Session, raw_token: str) -> tuple[Invitation, Family]:
    invitation = _get_valid_invitation(db, raw_token)
    family = db.get(Family, invitation.family_id)
    if family is None:
        raise InvitationError("Family no longer exists")
    return invitation, family


def accept_invitation(db: Session, raw_token: str, accepting_user_id: uuid.UUID) -> FamilyMembership:
    invitation = _get_valid_invitation(db, raw_token)

    try:
        membership = add_member(db, invitation.family_id, accepting_user_id, invitation.role)
    except FamilyError as exc:
        raise InvitationError(str(exc)) from exc

    invitation.status = InvitationStatus.ACCEPTED
    invitation.accepted_at = datetime.now(timezone.utc)
    db.commit()

    record_event(
        db,
        family_id=invitation.family_id,
        actor_user_id=accepting_user_id,
        action="invitation.accepted",
        entity_type="Invitation",
        entity_id=invitation.id,
        source_service="invitations",
    )
    return membership
