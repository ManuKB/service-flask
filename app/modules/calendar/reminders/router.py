import uuid

from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AppError
from app.core.responses import envelope, envelope_list
from app.modules.calendar.reminders import service
from app.modules.permissions.rbac import require_active_member
from app.schemas.calendar.reminders import (
    CreateReminderRequest,
    ProcessRemindersResponse,
    ReminderResponse,
    UpdateReminderRequest,
)

bp = Blueprint("calendar_reminders", __name__, url_prefix="/families/<uuid:family_id>/calendar")


@bp.post("/events/<uuid:event_id>/reminders")
def create_reminder(family_id: uuid.UUID, event_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = CreateReminderRequest(**request.get_json(force=True))
    try:
        reminder = service.create_reminder(db, family_id, user_id, event_id, payload.lead_time)
    except service.ReminderError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(ReminderResponse.model_validate(reminder), status.HTTP_201_CREATED)


@bp.get("/events/<uuid:event_id>/reminders")
def list_reminders(family_id: uuid.UUID, event_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    try:
        reminders = service.list_reminders(db, family_id, event_id)
    except service.ReminderError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope_list([ReminderResponse.model_validate(r) for r in reminders])


@bp.patch("/events/<uuid:event_id>/reminders/<uuid:reminder_id>")
def update_reminder(family_id: uuid.UUID, event_id: uuid.UUID, reminder_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = UpdateReminderRequest(**request.get_json(force=True))
    try:
        reminder = service.set_reminder_enabled(db, family_id, event_id, reminder_id, payload.is_enabled)
    except service.ReminderError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(ReminderResponse.model_validate(reminder))


@bp.post("/process-reminders")
def process_reminders(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    queued = service.process_due_reminders(db, family_id)
    return envelope(ProcessRemindersResponse(queued_reminder_ids=[reminder.id for reminder in queued]))
