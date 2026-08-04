import uuid
from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Time
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.modules.calendar.enums import ReminderLeadTime
from app.modules.finance.enums import BillReminderOffset


class Reminder(Base):
    __tablename__ = "calendar_reminders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Polymorphic target: exactly one of event_id/bill_id is set (enforced in
    # the service layer, not the DB) - lets the scheduler query due reminders
    # for both events and recurring bills in a single pass.
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("calendar_events.id"), nullable=True, index=True)
    bill_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("finance_recurring_bills.id"), nullable=True, index=True
    )
    # Event reminders: a duration before the event's own start_at (which
    # already carries a time-of-day).
    lead_time: Mapped[ReminderLeadTime | None] = mapped_column(Enum(ReminderLeadTime), nullable=True)
    # Bill reminders: a bill's due date has no time-of-day, so instead of a
    # single lead_time this pairs an offset from the due date with an
    # explicit clock time.
    bill_offset: Mapped[BillReminderOffset | None] = mapped_column(Enum(BillReminderOffset), nullable=True)
    remind_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Set once the reminder has been queued/delivered - also doubles as the
    # delivery record (S3-03: "reminder delivery is recorded") and the
    # idempotency guard ("queued once per event").
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
