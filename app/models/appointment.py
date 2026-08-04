import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class Appointment(Base):
    __tablename__ = "health_appointments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("health_patients.id"), nullable=False, index=True)
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("health_doctors.id"), nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set when the appointment was created with create_calendar_event=True
    # (S5-05: "Appointment can create a calendar event") - a real FK into
    # calendar-service's own table, same cross-module reuse pattern as
    # Notification.event_id/task_id.
    calendar_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("calendar_events.id"), nullable=True)
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
