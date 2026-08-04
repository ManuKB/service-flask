import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import status
from app.core.exceptions import AppError
from app.models.family_membership import FamilyMembership
from app.modules.permissions.roles import FamilyRole, MembershipStatus

# Reusable RBAC checks (S1-05 acceptance criteria: "permission checks are
# reusable by future modules"). FastAPI wired these in as `Depends(...)`
# parameters; Flask routes call them explicitly instead, same signature
# order (db, family_id, user_id) everywhere.


def get_membership(db: Session, family_id: uuid.UUID, user_id: uuid.UUID) -> FamilyMembership | None:
    return db.scalar(
        select(FamilyMembership).where(
            FamilyMembership.family_id == family_id,
            FamilyMembership.user_id == user_id,
        )
    )


def require_active_member(db: Session, family_id: uuid.UUID, user_id: uuid.UUID) -> FamilyMembership:
    membership = get_membership(db, family_id, user_id)
    if not membership or membership.status != MembershipStatus.ACTIVE:
        raise AppError(status.HTTP_403_FORBIDDEN, "Not an active member of this family")
    return membership


def require_owner(db: Session, family_id: uuid.UUID, user_id: uuid.UUID) -> FamilyMembership:
    membership = require_active_member(db, family_id, user_id)
    if membership.role != FamilyRole.OWNER:
        raise AppError(status.HTTP_403_FORBIDDEN, "Only the family owner can perform this action")
    return membership
