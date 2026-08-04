import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bill_completion import BillCompletion
from app.models.recurring_bill import RecurringBill
from app.models.reminder import Reminder
from app.modules.finance.dateutils import advance_due_date
from app.modules.finance.enums import BillCadence, BillReminderOffset, BillStatus, BillType, CategoryType
from app.modules.finance.reminders import get_reminder_sender
from app.modules.finance.transactions import service as transactions_service
from app.modules.notifications import service as notifications_service
from app.modules.notifications.push import service as push_service

# Offset from a bill's due date that each BillReminderOffset represents -
# paired with an explicit clock time (Reminder.remind_time) since a bill's
# due date alone has no time-of-day.
_BILL_OFFSET_DAYS = {
    BillReminderOffset.SAME_DAY: 0,
    BillReminderOffset.ONE_DAY_BEFORE: 1,
    BillReminderOffset.ONE_WEEK_BEFORE: 7,
}


class BillError(Exception):
    """Raised for any recurring-bill-domain failure the router should turn into an HTTP error."""


def create_bill(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    amount: float,
    bill_type: BillType,
    cadence: BillCadence,
    next_due_date: date,
    account_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
) -> RecurringBill:
    bill = RecurringBill(
        family_id=family_id,
        name=name,
        amount=Decimal(str(amount)),
        type=bill_type,
        cadence=cadence,
        next_due_date=next_due_date,
        account_id=account_id,
        category_id=category_id,
        status=BillStatus.ACTIVE,
        created_by_user_id=user_id,
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return bill


def list_bills(db: Session, family_id: uuid.UUID) -> list[RecurringBill]:
    result = db.scalars(
        select(RecurringBill).where(RecurringBill.family_id == family_id).order_by(RecurringBill.next_due_date)
    )
    return list(result)


def get_bill(db: Session, family_id: uuid.UUID, bill_id: uuid.UUID) -> RecurringBill:
    bill = db.get(RecurringBill, bill_id)
    if not bill or bill.family_id != family_id:
        raise BillError("Bill not found")
    return bill


def set_bill_status(
    db: Session, family_id: uuid.UUID, bill_id: uuid.UUID, new_status: BillStatus
) -> RecurringBill:
    bill = get_bill(db, family_id, bill_id)
    bill.status = new_status
    db.commit()
    db.refresh(bill)
    return bill


def send_reminder(db: Session, family_id: uuid.UUID, bill_id: uuid.UUID) -> RecurringBill:
    bill = get_bill(db, family_id, bill_id)
    get_reminder_sender().send_bill_reminder(family_id, bill.name, bill.amount, bill.next_due_date)
    return bill


# Scheduled reminders (Reminder rows, processed by the shared scheduler) -
# distinct from send_reminder() above, which is a manual one-shot console
# nudge. Mirrors app.modules.calendar.reminders.service's shape exactly.


def create_bill_reminder(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    bill_id: uuid.UUID,
    bill_offset: BillReminderOffset,
    remind_time: time,
) -> Reminder:
    get_bill(db, family_id, bill_id)
    reminder = Reminder(
        bill_id=bill_id,
        bill_offset=bill_offset,
        remind_time=remind_time,
        is_enabled=True,
        created_by_user_id=user_id,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


def list_bill_reminders(db: Session, family_id: uuid.UUID, bill_id: uuid.UUID) -> list[Reminder]:
    get_bill(db, family_id, bill_id)
    result = db.scalars(select(Reminder).where(Reminder.bill_id == bill_id).order_by(Reminder.created_at))
    return list(result)


def set_bill_reminder_enabled(
    db: Session, family_id: uuid.UUID, bill_id: uuid.UUID, reminder_id: uuid.UUID, is_enabled: bool
) -> Reminder:
    get_bill(db, family_id, bill_id)
    reminder = db.get(Reminder, reminder_id)
    if not reminder or reminder.bill_id != bill_id:
        raise BillError("Reminder not found")
    reminder.is_enabled = is_enabled
    db.commit()
    db.refresh(reminder)
    return reminder


def complete_bill(
    db: Session, family_id: uuid.UUID, user_id: uuid.UUID, bill_id: uuid.UUID, amount: float
) -> BillCompletion:
    """Marks the bill's current cycle complete: creates a real Transaction
    for the entered amount (which may differ from the bill's estimated
    amount), advances next_due_date to the next cycle (or, for a ONE_TIME
    bill, ends it - there is no next cycle), and records a BillCompletion
    row so the action can be undone. Also clears any pending reminder
    notification for this bill - it's done, so the "it's due" nudge is moot."""
    bill = get_bill(db, family_id, bill_id)
    if bill.status != BillStatus.ACTIVE:
        raise BillError("Only an active bill can be marked complete")
    if bill.account_id is None or bill.category_id is None:
        raise BillError("Set an account and category on this bill before marking it complete")

    category_type = CategoryType.INCOME if bill.type == BillType.INCOME else CategoryType.EXPENSE
    cycle_due_date = bill.next_due_date

    try:
        transaction = transactions_service.create_transaction(
            db,
            family_id,
            user_id,
            bill.account_id,
            bill.category_id,
            category_type,
            amount,
            cycle_due_date,
            f"Recurring {bill.type.value}: {bill.name}",
            None,
        )
    except transactions_service.TransactionError as exc:
        raise BillError(str(exc)) from exc

    completion = BillCompletion(
        family_id=family_id,
        bill_id=bill_id,
        cycle_due_date=cycle_due_date,
        amount=Decimal(str(amount)),
        transaction_id=transaction.id,
        completed_by_user_id=user_id,
    )
    db.add(completion)
    bill.next_due_date = advance_due_date(cycle_due_date, bill.cadence)
    if bill.cadence == BillCadence.ONE_TIME:
        bill.status = BillStatus.ENDED
    notifications_service.delete_notifications_for_bill(db, bill_id)
    db.commit()
    db.refresh(completion)
    return completion


def list_bill_completions(db: Session, family_id: uuid.UUID, bill_id: uuid.UUID) -> list[BillCompletion]:
    get_bill(db, family_id, bill_id)
    result = db.scalars(
        select(BillCompletion).where(BillCompletion.bill_id == bill_id).order_by(BillCompletion.completed_at.desc())
    )
    return list(result)


def undo_bill_completion(
    db: Session, family_id: uuid.UUID, user_id: uuid.UUID, bill_id: uuid.UUID, completion_id: uuid.UUID
) -> None:
    bill = get_bill(db, family_id, bill_id)
    completion = db.get(BillCompletion, completion_id)
    if not completion or completion.bill_id != bill_id:
        raise BillError("Completion not found")

    expected_next_due = advance_due_date(completion.cycle_due_date, bill.cadence)
    if bill.next_due_date != expected_next_due:
        raise BillError("Only the most recently completed cycle can be undone")

    transaction_id = completion.transaction_id
    cycle_due_date = completion.cycle_due_date

    # Delete (and flush) the completion row before its Transaction - it
    # holds the FK, and without an ORM relationship() linking the two, nothing
    # tells the unit of work to order a single flush that way on its own
    # (same class of bug as calendar.events.service.delete_event's fix).
    db.delete(completion)
    db.flush()

    transactions_service.delete_transaction(db, family_id, user_id, transaction_id)
    bill.next_due_date = cycle_due_date
    if bill.cadence == BillCadence.ONE_TIME:
        bill.status = BillStatus.ACTIVE
    db.commit()


def process_due_bill_reminders(
    db: Session, family_id: uuid.UUID, now: datetime | None = None
) -> list[Reminder]:
    """Bill counterpart of calendar.reminders.service.process_due_reminders -
    same idempotency guarantee (queued once), same real-delivery fan-out
    (in-app + push), called from the same shared scheduler pass per family.
    Each bill reminder fires at an explicit remind_time on the day computed
    from bill_offset (same day / 1 day before / 1 week before the due date);
    once `now` reaches that moment it fires - no upper bound is needed since
    queued_at already guarantees it only ever fires once."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is not None:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)

    result = db.execute(
        select(Reminder, RecurringBill)
        .join(RecurringBill, RecurringBill.id == Reminder.bill_id)
        .where(
            RecurringBill.family_id == family_id,
            RecurringBill.status == BillStatus.ACTIVE,
            Reminder.is_enabled.is_(True),
            Reminder.queued_at.is_(None),
        )
    )
    sender = get_reminder_sender()
    queued: list[Reminder] = []
    due_bills: list[RecurringBill] = []
    for reminder, bill in result.all():
        offset_days = _BILL_OFFSET_DAYS[reminder.bill_offset]
        remind_date = bill.next_due_date - timedelta(days=offset_days)
        remind_datetime = datetime.combine(remind_date, reminder.remind_time)
        if now >= remind_datetime:
            try:
                sender.send_bill_reminder(family_id, bill.name, bill.amount, bill.next_due_date)
            except Exception as exc:  # noqa: BLE001 - a console-log side effect must never block real queuing/delivery
                print(f"[finance] bill reminder console hook failed (ignored): {exc}")
            reminder.queued_at = now
            queued.append(reminder)
            due_bills.append(bill)

    if queued:
        db.commit()
        for reminder in queued:
            db.refresh(reminder)

        for bill in due_bills:
            title = f"{'Income' if bill.type == BillType.INCOME else 'Bill'} reminder"
            body = f"{bill.name} (${bill.amount}) is due {bill.next_due_date.strftime('%b %d, %Y')}"
            notifications = notifications_service.notify_family(db, family_id, title, body, bill_id=bill.id)
            db.commit()
            for notification in notifications:
                push_service.send_web_push_to_user(db, notification.user_id, title, body)

    return queued
