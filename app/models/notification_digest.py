import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class NotificationDigestRun(Base):
    """One row per family per day per slot ("morning"/"evening") that the
    9 AM / 7 PM overdue digest has already fired for - the idempotency guard
    so a family isn't re-notified every scheduler tick within the same slot."""

    __tablename__ = "notification_digest_runs"
    __table_args__ = (UniqueConstraint("family_id", "run_date", "slot", name="uq_digest_family_date_slot"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("families.id"), nullable=False, index=True)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    slot: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
