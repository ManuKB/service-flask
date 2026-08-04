import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.modules.finance.enums import BillCadence, BillStatus, BillType


class RecurringBill(Base):
    __tablename__ = "finance_recurring_bills"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("families.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # Direction independent of category - category_id is optional, so this is
    # the only reliable source of truth for what a completion's Transaction.type should be.
    type: Mapped[BillType] = mapped_column(Enum(BillType), nullable=False, default=BillType.BILL)
    cadence: Mapped[BillCadence] = mapped_column(Enum(BillCadence), nullable=False)
    next_due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("finance_accounts.id"), nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("finance_categories.id"), nullable=True)
    status: Mapped[BillStatus] = mapped_column(Enum(BillStatus), nullable=False, default=BillStatus.ACTIVE)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
