import uuid

from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.responses import envelope, envelope_list
from app.modules.calendar.calendars import service
from app.modules.permissions.rbac import require_active_member
from app.schemas.calendar.calendars import CalendarResponse, CreateCalendarRequest

bp = Blueprint("calendar_calendars", __name__, url_prefix="/families/<uuid:family_id>/calendar/calendars")


@bp.get("")
def list_calendars(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    calendars = service.list_calendars(db, family_id, user_id)
    return envelope_list([CalendarResponse.model_validate(c) for c in calendars])


@bp.post("")
def create_calendar(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = CreateCalendarRequest(**request.get_json(force=True))
    calendar = service.create_calendar(db, family_id, user_id, payload.name)
    return envelope(CalendarResponse.model_validate(calendar), status.HTTP_201_CREATED)
