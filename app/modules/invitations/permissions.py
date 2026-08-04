import uuid

from sqlalchemy.orm import Session

from app.core import status
from app.core.exceptions import AppError
from app.modules.permissions.rbac import get_membership
from app.modules.permissions.roles import FamilyRole, MembershipStatus


def require_family_owner(db: Session, family_id: uuid.UUID, user_id: uuid.UUID) -> uuid.UUID:
    membership = get_membership(db, family_id, user_id)
    if not membership or membership.role != FamilyRole.OWNER or membership.status != MembershipStatus.ACTIVE:
        raise AppError(status.HTTP_403_FORBIDDEN, "Only the family owner can invite members")
    return user_id
