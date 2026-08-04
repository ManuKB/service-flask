import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.reminder import Reminder
from app.modules.calendar.enums import ReminderLeadTime
from app.modules.calendar.notifications import get_notification_sender
from app.modules.calendar.recurrence import to_utc_naive
from app.modules.notifications import service as notifications_service
from app.modules.notifications.push import service as push_service


class ReminderError(Exception):
    """Raised for any reminder-domain failure the router should turn into an HTTP error."""


def _get_event(db: Session, family_id: uuid.UUID, event_id: uuid.UUID) -> Event:
    event = db.get(Event, event_id)
    if not event or event.family_id != family_id or event.parent_event_id is not None:
        raise ReminderError("Event not found")
    return event


def create_reminder(
    db: Session, family_id: uuid.UUID, user_id: uuid.UUID, event_id: uuid.UUID, lead_time: ReminderLeadTime
) -> Reminder:
    _get_event(db, family_id, event_id)
    reminder = Reminder(event_id=event_id, lead_time=lead_time, is_enabled=True, created_by_user_id=user_id)
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


def list_reminders(db: Session, family_id: uuid.UUID, event_id: uuid.UUID) -> list[Reminder]:
    _get_event(db, family_id, event_id)
    result = db.scalars(select(Reminder).where(Reminder.event_id == event_id).order_by(Reminder.created_at))
    return list(result)


def set_reminder_enabled(
    db: Session, family_id: uuid.UUID, event_id: uuid.UUID, reminder_id: uuid.UUID, is_enabled: bool
) -> Reminder:
    _get_event(db, family_id, event_id)
    reminder = db.get(Reminder, reminder_id)
    if not reminder or reminder.event_id != event_id:
        raise ReminderError("Reminder not found")
    reminder.is_enabled = is_enabled
    db.commit()
    db.refresh(reminder)
    return reminder


def process_due_reminders(db: Session, family_id: uuid.UUID, now: datetime | None = None) -> list[Reminder]:
    """Scans this family's enabled, not-yet-queued reminders and queues
    (calls the notification hook + records queued_at) any whose event is due
    within their lead time. Idempotent: a reminder is only ever queued once
    (S3-03: "queued once per event"); disabled reminders are skipped
    entirely ("disabled reminder is not sent")."""
    now = to_utc_naive(now or datetime.now(timezone.utc))

    result = db.execute(
        select(Reminder, Event)
        .join(Event, Event.id == Reminder.event_id)
        .where(
            Event.family_id == family_id,
            Reminder.is_enabled.is_(True),
            Reminder.queued_at.is_(None),
        )
    )
    sender = get_notification_sender()
    queued: list[Reminder] = []
    due_events: list[Event] = []
    for reminder, event in result.all():
        event_start = to_utc_naive(event.start_at)
        remind_at = event_start - reminder.lead_time.as_timedelta()
        if remind_at <= now <= event_start:
            try:
                sender.send_event_reminder(family_id, event.title, event.start_at)
            except Exception as exc:  # noqa: BLE001 - a console-log side effect must never block real queuing/delivery
                print(f"[calendar] reminder console hook failed (ignored): {exc}")
            reminder.queued_at = now
            queued.append(reminder)
            due_events.append(event)

    if queued:
        db.commit()
        for reminder in queued:
            db.refresh(reminder)

        # Real delivery (in-app feed + best-effort web push) - fanned out to
        # every active family member, one event at a time so a push failure
        # for one member/event never blocks another's in-app notification.
        for event in due_events:
            title = "Event reminder"
            body = f"{event.title} starts at {event.start_at.strftime('%b %d, %I:%M %p')}"
            notifications = notifications_service.notify_family(db, family_id, title, body, event.id)
            db.commit()
            for notification in notifications:
                push_service.send_web_push_to_user(db, notification.user_id, title, body)

    return queued
