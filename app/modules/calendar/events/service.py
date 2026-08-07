import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.calendar import Calendar
from app.models.event import Event
from app.models.event_participant import EventParticipant
from app.models.family_membership import FamilyMembership
from app.models.notification import Notification
from app.models.reminder import Reminder
from app.modules.calendar.enums import RecurrenceFrequency, ReminderLeadTime
from app.modules.calendar.recurrence import format_weekdays, to_utc_naive
from app.modules.notifications import service as notifications_service


class EventError(Exception):
    """Raised for any event-domain failure the router should turn into an HTTP error."""


def _validate_participants(db: Session, family_id: uuid.UUID, user_ids: list[uuid.UUID]) -> None:
    for user_id in set(user_ids):
        membership = db.scalar(
            select(FamilyMembership).where(
                FamilyMembership.family_id == family_id, FamilyMembership.user_id == user_id
            )
        )
        if not membership:
            raise EventError(f"User {user_id} is not a member of this family")


def _validate_calendar(db: Session, family_id: uuid.UUID, calendar_id: uuid.UUID) -> Calendar:
    calendar = db.get(Calendar, calendar_id)
    if not calendar or calendar.family_id != family_id:
        raise EventError("Calendar not found")
    return calendar


def _set_participants(db: Session, event_id: uuid.UUID, user_ids: list[uuid.UUID]) -> None:
    existing = db.scalars(select(EventParticipant).where(EventParticipant.event_id == event_id))
    for row in existing:
        db.delete(row)
    for user_id in set(user_ids):
        db.add(EventParticipant(event_id=event_id, user_id=user_id))


def get_participant_ids(db: Session, event_id: uuid.UUID) -> list[uuid.UUID]:
    result = db.scalars(select(EventParticipant.user_id).where(EventParticipant.event_id == event_id))
    return list(result)


def create_event(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    calendar_id: uuid.UUID,
    title: str,
    description: str | None,
    location: str | None,
    start_at: datetime,
    end_at: datetime,
    participant_user_ids: list[uuid.UUID],
    recurrence_frequency: RecurrenceFrequency | None,
    recurrence_interval: int,
    recurrence_by_weekday: list[int] | None,
    recurrence_end_date: date | None,
) -> Event:
    _validate_calendar(db, family_id, calendar_id)
    _validate_participants(db, family_id, participant_user_ids)

    event = Event(
        family_id=family_id,
        calendar_id=calendar_id,
        title=title,
        description=description,
        location=location,
        start_at=start_at,
        end_at=end_at,
        recurrence_frequency=recurrence_frequency,
        recurrence_interval=recurrence_interval,
        recurrence_by_weekday=format_weekdays(recurrence_by_weekday),
        recurrence_end_date=recurrence_end_date,
        created_by_user_id=user_id,
    )
    db.add(event)
    db.flush()
    _set_participants(db, event.id, participant_user_ids)
    # Every event gets a 1-hour-before reminder automatically - no manual
    # setup required. The user can still disable it or add more from the
    # event detail view.
    db.add(Reminder(event_id=event.id, lead_time=ReminderLeadTime.ONE_HOUR, is_enabled=True, created_by_user_id=user_id))
    db.commit()
    db.refresh(event)
    return event


def get_event(db: Session, family_id: uuid.UUID, event_id: uuid.UUID) -> Event:
    event = db.get(Event, event_id)
    if not event or event.family_id != family_id or event.parent_event_id is not None:
        raise EventError("Event not found")
    return event


def update_event(
    db: Session,
    family_id: uuid.UUID,
    event_id: uuid.UUID,
    *,
    calendar_id: uuid.UUID | None = None,
    title: str | None = None,
    description: str | None = None,
    location: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    participant_user_ids: list[uuid.UUID] | None = None,
    recurrence_frequency: RecurrenceFrequency | None = None,
    recurrence_interval: int | None = None,
    recurrence_by_weekday: list[int] | None = None,
    recurrence_end_date: date | None = None,
    clear_recurrence: bool = False,
) -> Event:
    event = get_event(db, family_id, event_id)

    effective_start = start_at if start_at is not None else event.start_at
    effective_end = end_at if end_at is not None else event.end_at
    if effective_end < effective_start:
        raise EventError("end_at cannot precede start_at")

    if calendar_id is not None:
        _validate_calendar(db, family_id, calendar_id)
        event.calendar_id = calendar_id
    if title is not None:
        event.title = title
    if description is not None:
        event.description = description
    if location is not None:
        event.location = location
    event.start_at = effective_start
    event.end_at = effective_end

    if clear_recurrence:
        event.recurrence_frequency = None
        event.recurrence_interval = 1
        event.recurrence_by_weekday = None
        event.recurrence_end_date = None
    elif recurrence_frequency is not None:
        event.recurrence_frequency = recurrence_frequency
        event.recurrence_interval = recurrence_interval or 1
        event.recurrence_by_weekday = format_weekdays(recurrence_by_weekday)
        event.recurrence_end_date = recurrence_end_date

    if participant_user_ids is not None:
        _validate_participants(db, family_id, participant_user_ids)
        _set_participants(db, event.id, participant_user_ids)

    db.commit()
    db.refresh(event)
    return event


def delete_event(db: Session, family_id: uuid.UUID, event_id: uuid.UUID) -> None:
    event = get_event(db, family_id, event_id)

    if event.recurrence_frequency is None and event.is_completed:
        raise EventError("Undo the completed status before deleting this event")

    exceptions = list(db.scalars(select(Event).where(Event.parent_event_id == event_id)))
    completed_exceptions = [exc for exc in exceptions if exc.is_completed]

    if completed_exceptions:
        # Soft-end instead of a real delete: completed occurrences are kept
        # as history (and, transitively, so is the base event they point
        # back to via parent_event_id - deleting it would need to delete
        # them too, which is exactly what we're trying to avoid). Only the
        # not-yet-completed occurrences and the series' own future
        # reminders are purged; recurrence_end_date is capped so the series
        # stops generating anything beyond the last completed occurrence.
        for exc in exceptions:
            if not exc.is_completed:
                db.delete(exc)
        latest_completed_date = max(exc.occurrence_date for exc in completed_exceptions)
        if event.recurrence_end_date is None or event.recurrence_end_date > latest_completed_date:
            event.recurrence_end_date = latest_completed_date
        reminders = db.scalars(select(Reminder).where(Reminder.event_id == event_id))
        for reminder in reminders:
            db.delete(reminder)
        db.commit()
        return

    for exc in exceptions:
        db.delete(exc)
    participants = db.scalars(select(EventParticipant).where(EventParticipant.event_id == event_id))
    for participant in participants:
        db.delete(participant)
    reminders = db.scalars(select(Reminder).where(Reminder.event_id == event_id))
    for reminder in reminders:
        db.delete(reminder)
    # Any reminder that already fired left behind Notification rows pointing
    # at this event (event_id is a real FK) - those must go too, or SQLite's
    # foreign_keys=ON rejects the delete.
    notifications = db.scalars(select(Notification).where(Notification.event_id == event_id))
    for notification in notifications:
        db.delete(notification)

    # Flush the dependents' deletes first: without an ORM relationship()
    # linking Event to these tables, the unit of work has no dependency
    # info to order a single flush correctly, so the event's own DELETE can
    # get sent before its children's and trip the FK constraint.
    db.flush()
    db.delete(event)
    db.commit()


def _get_or_create_exception(db: Session, family_id: uuid.UUID, event_id: uuid.UUID, occurrence_date: date) -> Event:
    parent = get_event(db, family_id, event_id)
    if parent.recurrence_frequency is None:
        raise EventError("This event does not repeat, so it has no individual occurrences to edit")

    existing = db.scalar(
        select(Event).where(Event.parent_event_id == event_id, Event.occurrence_date == occurrence_date)
    )
    if existing:
        return existing

    parent_start = to_utc_naive(parent.start_at)
    duration = to_utc_naive(parent.end_at) - parent_start
    occurrence_start = datetime.combine(occurrence_date, parent_start.time())

    exception = Event(
        family_id=family_id,
        calendar_id=parent.calendar_id,
        title=parent.title,
        description=parent.description,
        location=parent.location,
        start_at=occurrence_start,
        end_at=occurrence_start + duration,
        parent_event_id=event_id,
        occurrence_date=occurrence_date,
        is_cancelled=False,
        created_by_user_id=parent.created_by_user_id,
    )
    db.add(exception)
    db.flush()
    return exception


def update_occurrence(
    db: Session,
    family_id: uuid.UUID,
    event_id: uuid.UUID,
    occurrence_date: date,
    *,
    title: str | None = None,
    description: str | None = None,
    location: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> Event:
    exception = _get_or_create_exception(db, family_id, event_id, occurrence_date)

    effective_start = start_at if start_at is not None else exception.start_at
    effective_end = end_at if end_at is not None else exception.end_at
    if effective_end < effective_start:
        raise EventError("end_at cannot precede start_at")

    if title is not None:
        exception.title = title
    if description is not None:
        exception.description = description
    if location is not None:
        exception.location = location
    exception.start_at = effective_start
    exception.end_at = effective_end
    exception.is_cancelled = False

    db.commit()
    db.refresh(exception)
    return exception


def cancel_occurrence(db: Session, family_id: uuid.UUID, event_id: uuid.UUID, occurrence_date: date) -> None:
    exception = _get_or_create_exception(db, family_id, event_id, occurrence_date)
    if exception.is_completed:
        raise EventError("Undo the completed status before removing this occurrence")
    exception.is_cancelled = True
    db.commit()


def complete_occurrence(db: Session, family_id: uuid.UUID, event_id: uuid.UUID, occurrence_date: date) -> Event:
    """Generic 'mark as complete' - no amount involved (see finance.bills
    for the amount-bearing bill/income completion flow). A non-recurring
    event has no occurrence-exception rows at all, so its own base row
    carries completion state directly; a recurring event's completion is
    always scoped to one occurrence, materialized the same way
    update_occurrence/cancel_occurrence already do."""
    event = get_event(db, family_id, event_id)
    target = event if event.recurrence_frequency is None else _get_or_create_exception(
        db, family_id, event_id, occurrence_date
    )
    target.is_completed = True
    target.completed_at = to_utc_naive(datetime.now(timezone.utc))
    target.is_cancelled = False
    # The reminder notification (if any fired) is moot now - it's done.
    # event_id here is always the base event's id (reminders only ever
    # attach to the base row, never an occurrence-exception), so this
    # clears the one relevant notification regardless of which occurrence
    # was completed.
    notifications_service.delete_notifications_for_event(db, event_id)
    db.commit()
    db.refresh(target)
    return target


def undo_occurrence_completion(
    db: Session, family_id: uuid.UUID, event_id: uuid.UUID, occurrence_date: date
) -> Event:
    event = get_event(db, family_id, event_id)
    if event.recurrence_frequency is None:
        target = event
    else:
        target = db.scalar(
            select(Event).where(Event.parent_event_id == event_id, Event.occurrence_date == occurrence_date)
        )
        if target is None:
            raise EventError("This occurrence has not been completed")

    if not target.is_completed:
        raise EventError("This item has not been completed")

    target.is_completed = False
    target.completed_at = None
    db.commit()
    db.refresh(target)
    return target
