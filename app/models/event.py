import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.modules.calendar.enums import RecurrenceFrequency


class Event(Base):
    __tablename__ = "calendar_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("families.id"), nullable=False, index=True)
    calendar_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calendars.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Recurrence (S3-04). A null frequency means a single, non-repeating event.
    recurrence_frequency: Mapped[RecurrenceFrequency | None] = mapped_column(
        Enum(RecurrenceFrequency), nullable=True
    )
    recurrence_interval: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Comma-separated weekday ints (Monday=0..Sunday=6), weekly recurrence only.
    recurrence_by_weekday: Mapped[str | None] = mapped_column(String(20), nullable=True)
    recurrence_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Occurrence exception: when set, this row overrides (or cancels, via
    # is_cancelled) a single occurrence of the recurring parent event instead
    # of being a standalone event itself.
    parent_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("calendar_events.id"), nullable=True, index=True)
    occurrence_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Occurrence completion (generic "mark as complete", no amount involved -
    # see finance.bills for the amount-bearing bill/income completion flow).
    # Only ever set on occurrence-exception rows (parent_event_id is not None).
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
