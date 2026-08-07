import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification_digest import NotificationDigestRun
from app.models.recurring_bill import RecurringBill
from app.models.task import Task
from app.modules.calendar.agenda.service import get_agenda
from app.modules.finance.enums import BillStatus
from app.modules.notifications import service as notifications_service
from app.modules.notifications.push import service as push_service
from app.modules.tasks.enums import TaskStatus

_DIGEST_TIMEZONE = ZoneInfo("Asia/Kolkata")
# (slot name, hour-of-day in _DIGEST_TIMEZONE the digest becomes eligible to fire)
_DIGEST_SLOTS = [("morning", 9), ("evening", 19)]
# How far back to look for overdue event occurrences - unbounded lookback
# would mean expanding forever-recurring events from the beginning of time.
_EVENT_LOOKBACK_DAYS = 30


def _overdue_counts(db: Session, family_id: uuid.UUID, today: date, now_utc: datetime) -> tuple[int, int, int]:
    task_count = len(
        list(
            db.scalars(
                select(Task.id).where(
                    Task.family_id == family_id, Task.status != TaskStatus.DONE, Task.due_date.isnot(None), Task.due_date < today
                )
            )
        )
    )

    bill_count = len(
        list(
            db.scalars(
                select(RecurringBill.id).where(
                    RecurringBill.family_id == family_id,
                    RecurringBill.status == BillStatus.ACTIVE,
                    RecurringBill.next_due_date < today,
                )
            )
        )
    )

    window_start = today - timedelta(days=_EVENT_LOOKBACK_DAYS)
    pairs = get_agenda(db, family_id, window_start, today)
    event_count = sum(1 for _event, occ in pairs if not occ.is_completed and occ.end_at < now_utc)

    return task_count, bill_count, event_count


def process_daily_digest(db: Session, family_id: uuid.UUID, now: datetime | None = None) -> None:
    """Sends a once-per-slot-per-day push/in-app summary of everything
    currently overdue (tasks past their due date, bills past their next due
    date, event occurrences past their end time and not marked done) at
    9 AM and 7 PM Asia/Kolkata time - fully automatic, no per-item setup."""
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    now_local = now_utc.astimezone(_DIGEST_TIMEZONE)
    today = now_local.date()

    for slot, eligible_hour in _DIGEST_SLOTS:
        if now_local.hour < eligible_hour:
            continue
        already_sent = db.scalar(
            select(NotificationDigestRun).where(
                NotificationDigestRun.family_id == family_id,
                NotificationDigestRun.run_date == today,
                NotificationDigestRun.slot == slot,
            )
        )
        if already_sent:
            continue

        task_count, bill_count, event_count = _overdue_counts(db, family_id, today, now_utc.replace(tzinfo=None))
        if task_count or bill_count or event_count:
            parts = []
            if task_count:
                parts.append(f"{task_count} task{'s' if task_count != 1 else ''}")
            if bill_count:
                parts.append(f"{bill_count} bill{'s' if bill_count != 1 else ''}")
            if event_count:
                parts.append(f"{event_count} event{'s' if event_count != 1 else ''}")
            title = "Overdue items"
            body = f"You have {', '.join(parts)} overdue."
            notifications = notifications_service.notify_family(db, family_id, title, body)
            db.commit()
            for notification in notifications:
                push_service.send_web_push_to_user(db, notification.user_id, title, body)

        db.add(NotificationDigestRun(family_id=family_id, run_date=today, slot=slot))
        db.commit()
