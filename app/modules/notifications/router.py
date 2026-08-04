import uuid

from flask import Blueprint

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.responses import envelope, envelope_list, no_content
from app.core import status
from app.core.exceptions import AppError
from app.modules.notifications import service
from app.modules.permissions.rbac import require_active_member
from app.schemas.notifications import NotificationResponse, UnreadCountResponse

bp = Blueprint("notifications", __name__, url_prefix="/families/<uuid:family_id>/notifications")


@bp.get("")
def list_notifications(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    notifications = service.list_notifications(db, family_id, user_id)
    return envelope_list([NotificationResponse.model_validate(n) for n in notifications])


@bp.get("/unread-count")
def unread_count(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    count = service.get_unread_count(db, family_id, user_id)
    return envelope(UnreadCountResponse(unread_count=count))


@bp.post("/mark-all-read")
def mark_all_read(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    service.mark_all_read(db, family_id, user_id)
    return no_content()


@bp.post("/<uuid:notification_id>/read")
def mark_read(family_id: uuid.UUID, notification_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    try:
        notification = service.mark_read(db, family_id, user_id, notification_id)
    except service.NotificationError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(NotificationResponse.model_validate(notification))


@bp.delete("")
def clear_all_notifications(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    service.clear_all_notifications(db, family_id, user_id)
    return no_content()


@bp.delete("/<uuid:notification_id>")
def delete_notification(family_id: uuid.UUID, notification_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    try:
        service.delete_notification(db, family_id, user_id, notification_id)
    except service.NotificationError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return no_content()
