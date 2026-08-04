import threading

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.family import Family
from app.modules.calendar.reminders.service import process_due_reminders
from app.modules.finance.bills.service import process_due_bill_reminders
from app.modules.tasks.service import process_due_task_reminders


def _run_once() -> None:
    """Single shared pass, per family, for calendar-event reminders,
    recurring-bill reminders, and task due-soon/overdue reminders - one
    interval, one scheduler tick, covering all three kinds. Each kind is
    isolated in its own try/except so a failure in one (or one family) never
    blocks another kind or any other family from being processed."""
    with SessionLocal() as db:
        family_ids = list(db.scalars(select(Family.id)))
        for family_id in family_ids:
            try:
                process_due_reminders(db, family_id)
            except Exception as exc:  # noqa: BLE001 - one family's failure must not stop the rest
                print(f"[scheduler] event reminder processing failed for family {family_id}: {exc}")
                db.rollback()  # keep the shared session usable for the next family/kind

            try:
                process_due_bill_reminders(db, family_id)
            except Exception as exc:  # noqa: BLE001 - one family's failure must not stop the rest
                print(f"[scheduler] bill reminder processing failed for family {family_id}: {exc}")
                db.rollback()

            try:
                process_due_task_reminders(db, family_id)
            except Exception as exc:  # noqa: BLE001 - one family's failure must not stop the rest
                print(f"[scheduler] task reminder processing failed for family {family_id}: {exc}")
                db.rollback()


def _run_forever(interval_seconds: int, stop_event: threading.Event) -> None:
    while not stop_event.wait(interval_seconds):
        _run_once()


def start_reminder_scheduler() -> threading.Event:
    """Periodic in-process background thread (no external cron exists, so
    the app schedules itself) that calls the three reminder passes for every
    family on an interval. FastAPI ran this as an asyncio.Task; Flask's WSGI
    workers have no event loop, so a daemon thread is the equivalent here.
    Returns the stop_event used to cancel it on shutdown - see app/main.py."""
    interval_seconds = get_settings().reminder_scheduler_interval_seconds
    stop_event = threading.Event()
    thread = threading.Thread(
        target=_run_forever, args=(interval_seconds, stop_event), daemon=True, name="reminder-scheduler"
    )
    thread.start()
    return stop_event
