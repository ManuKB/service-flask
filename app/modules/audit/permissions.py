import uuid

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AppError
from app.modules.permissions.rbac import get_membership
from app.modules.permissions.roles import MembershipStatus


def require_family_member(family_id: uuid.UUID) -> uuid.UUID:
    """Enforces 'family members cannot see other families' audit events' via
    the shared RBAC membership check."""
    user_id = get_current_user_id()
    membership = get_membership(get_db(), family_id, user_id)
    if not membership or membership.status != MembershipStatus.ACTIVE:
        raise AppError(status.HTTP_403_FORBIDDEN, "Not an active member of this family")
    return user_id
