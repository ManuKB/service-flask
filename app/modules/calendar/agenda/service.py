import uuid
from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import Event
from app.modules.calendar.recurrence import Occurrence, expand_event, to_utc_naive


def get_agenda(db: Session, family_id: uuid.UUID, start: date, end: date) -> list[tuple[Event, Occurrence]]:
    """Expands recurring events bounded to [start, end) only (S3-04: "Agenda
    expands only the required date range") - no unbounded/infinite expansion."""
    range_start = datetime.combine(start, time.min)
    range_end = datetime.combine(end, time.min)

    base_events_result = db.scalars(
        select(Event).where(
            Event.family_id == family_id,
            Event.parent_event_id.is_(None),
            Event.start_at < range_end,
        )
    )
    base_events = list(base_events_result)

    exceptions_result = db.scalars(
        select(Event).where(Event.family_id == family_id, Event.parent_event_id.isnot(None))
    )
    exceptions_by_parent: dict[uuid.UUID, list[Event]] = {}
    for exc in exceptions_result:
        exceptions_by_parent.setdefault(exc.parent_event_id, []).append(exc)

    pairs: list[tuple[Event, Occurrence]] = []
    for event in base_events:
        if event.recurrence_frequency is None and to_utc_naive(event.end_at) < range_start:
            continue
        if event.recurrence_end_date is not None and event.recurrence_end_date < start:
            continue
        for occ in expand_event(event, exceptions_by_parent.get(event.id, []), range_start, range_end):
            pairs.append((event, occ))

    pairs.sort(key=lambda pair: pair[1].start_at)
    return pairs
