import uuid
from datetime import date, timedelta

from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AppError
from app.core.responses import envelope
from app.modules.calendar.agenda import service
from app.modules.calendar.events.service import get_participant_ids
from app.modules.permissions.rbac import require_active_member
from app.schemas.calendar.agenda import AgendaOccurrenceResponse, AgendaResponse

bp = Blueprint("calendar_agenda", __name__, url_prefix="/families/<uuid:family_id>/calendar")


def _parse_date_arg(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@bp.get("/agenda")
def get_agenda(family_id: uuid.UUID):
    db = get_db()
    user_id = get_current_user_id()
    require_active_member(db, family_id, user_id)

    start = _parse_date_arg(request.args.get("start"))
    end = _parse_date_arg(request.args.get("end"))

    range_start = start or date.today()
    range_end = end or (range_start + timedelta(days=7))

    pairs = service.get_agenda(db, family_id, range_start, range_end)

    occurrence_responses = []
    for event, occ in pairs:
        participant_ids = get_participant_ids(db, event.id)
        occurrence_responses.append(
            AgendaOccurrenceResponse(
                event_id=event.id,
                calendar_id=event.calendar_id,
                title=occ.title,
                description=occ.description,
                location=occ.location,
                occurrence_date=occ.occurrence_date,
                start_at=occ.start_at,
                end_at=occ.end_at,
                is_recurring=event.recurrence_frequency is not None,
                is_exception=occ.is_exception,
                is_completed=occ.is_completed,
                participant_user_ids=participant_ids,
            )
        )

    return envelope(AgendaResponse(start=range_start, end=range_end, occurrences=occurrence_responses))
