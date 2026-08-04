import uuid
from datetime import date

from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AppError
from app.core.responses import envelope, no_content
from app.models.event import Event
from app.modules.calendar.events import service
from app.modules.calendar.recurrence import parse_weekdays
from app.modules.permissions.rbac import require_active_member
from app.schemas.calendar.events import (
    CreateEventRequest,
    EventResponse,
    RecurrenceInfo,
    UpdateEventRequest,
    UpdateOccurrenceRequest,
)

bp = Blueprint("calendar_events", __name__, url_prefix="/families/<uuid:family_id>/calendar/events")


def _parse_occurrence_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


def _to_event_response(db, event: Event) -> EventResponse:
    participant_ids = service.get_participant_ids(db, event.id)
    recurrence = None
    if event.recurrence_frequency is not None:
        recurrence = RecurrenceInfo(
            frequency=event.recurrence_frequency,
            interval=event.recurrence_interval,
            by_weekday=parse_weekdays(event.recurrence_by_weekday),
            end_date=event.recurrence_end_date,
        )
    return EventResponse(
        id=event.id,
        family_id=event.family_id,
        calendar_id=event.calendar_id,
        title=event.title,
        description=event.description,
        location=event.location,
        start_at=event.start_at,
        end_at=event.end_at,
        recurrence=recurrence,
        participant_user_ids=participant_ids,
        is_completed=event.is_completed,
        completed_at=event.completed_at,
        created_by_user_id=event.created_by_user_id,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


@bp.post("")
def create_event(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = CreateEventRequest(**request.get_json(force=True))
    try:
        event = service.create_event(
            db,
            family_id,
            user_id,
            payload.calendar_id,
            payload.title,
            payload.description,
            payload.location,
            payload.start_at,
            payload.end_at,
            payload.participant_user_ids,
            payload.recurrence.frequency if payload.recurrence else None,
            payload.recurrence.interval if payload.recurrence else 1,
            payload.recurrence.by_weekday if payload.recurrence else None,
            payload.recurrence.end_date if payload.recurrence else None,
        )
    except service.EventError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return envelope(_to_event_response(db, event), status.HTTP_201_CREATED)


@bp.get("/<uuid:event_id>")
def get_event(family_id: uuid.UUID, event_id: uuid.UUID):
    db = get_db()
    user_id = get_current_user_id()
    require_active_member(db, family_id, user_id)
    try:
        event = service.get_event(db, family_id, event_id)
    except service.EventError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(_to_event_response(db, event))


@bp.patch("/<uuid:event_id>")
def update_event(family_id: uuid.UUID, event_id: uuid.UUID):
    db = get_db()
    user_id = get_current_user_id()
    require_active_member(db, family_id, user_id)
    payload = UpdateEventRequest(**request.get_json(force=True))
    try:
        event = service.update_event(
            db,
            family_id,
            event_id,
            calendar_id=payload.calendar_id,
            title=payload.title,
            description=payload.description,
            location=payload.location,
            start_at=payload.start_at,
            end_at=payload.end_at,
            participant_user_ids=payload.participant_user_ids,
            recurrence_frequency=payload.recurrence.frequency if payload.recurrence else None,
            recurrence_interval=payload.recurrence.interval if payload.recurrence else None,
            recurrence_by_weekday=payload.recurrence.by_weekday if payload.recurrence else None,
            recurrence_end_date=payload.recurrence.end_date if payload.recurrence else None,
            clear_recurrence=payload.clear_recurrence,
        )
    except service.EventError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return envelope(_to_event_response(db, event))


@bp.delete("/<uuid:event_id>")
def delete_event(family_id: uuid.UUID, event_id: uuid.UUID):
    db = get_db()
    user_id = get_current_user_id()
    require_active_member(db, family_id, user_id)
    # Checked separately from the delete itself so "doesn't exist" (404) and
    # "exists but is blocked from deletion" (400, e.g. still marked complete)
    # map to different status codes instead of both collapsing to 404.
    try:
        service.get_event(db, family_id, event_id)
    except service.EventError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    try:
        service.delete_event(db, family_id, event_id)
    except service.EventError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return no_content()


@bp.patch("/<uuid:event_id>/occurrences/<occurrence_date>")
def update_occurrence(family_id: uuid.UUID, event_id: uuid.UUID, occurrence_date: str):
    db = get_db()
    user_id = get_current_user_id()
    require_active_member(db, family_id, user_id)
    parsed_date = _parse_occurrence_date(occurrence_date)
    payload = UpdateOccurrenceRequest(**request.get_json(force=True))
    try:
        exception = service.update_occurrence(
            db,
            family_id,
            event_id,
            parsed_date,
            title=payload.title,
            description=payload.description,
            location=payload.location,
            start_at=payload.start_at,
            end_at=payload.end_at,
        )
    except service.EventError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return envelope(_to_event_response(db, exception))


@bp.delete("/<uuid:event_id>/occurrences/<occurrence_date>")
def cancel_occurrence(family_id: uuid.UUID, event_id: uuid.UUID, occurrence_date: str):
    db = get_db()
    user_id = get_current_user_id()
    require_active_member(db, family_id, user_id)
    parsed_date = _parse_occurrence_date(occurrence_date)
    try:
        service.cancel_occurrence(db, family_id, event_id, parsed_date)
    except service.EventError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return no_content()


@bp.post("/<uuid:event_id>/occurrences/<occurrence_date>/complete")
def complete_occurrence(family_id: uuid.UUID, event_id: uuid.UUID, occurrence_date: str):
    db = get_db()
    user_id = get_current_user_id()
    require_active_member(db, family_id, user_id)
    parsed_date = _parse_occurrence_date(occurrence_date)
    try:
        target = service.complete_occurrence(db, family_id, event_id, parsed_date)
    except service.EventError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return envelope(_to_event_response(db, target))


@bp.post("/<uuid:event_id>/occurrences/<occurrence_date>/undo-complete")
def undo_occurrence_completion(family_id: uuid.UUID, event_id: uuid.UUID, occurrence_date: str):
    db = get_db()
    user_id = get_current_user_id()
    require_active_member(db, family_id, user_id)
    parsed_date = _parse_occurrence_date(occurrence_date)
    try:
        target = service.undo_occurrence_completion(db, family_id, event_id, parsed_date)
    except service.EventError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return envelope(_to_event_response(db, target))
