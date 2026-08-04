import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.modules.finance.enums import BillCadence, BillReminderOffset, BillStatus, BillType


class CreateBillRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    amount: float = Field(gt=0)
    type: BillType = BillType.BILL
    cadence: BillCadence
    next_due_date: date
    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None


class UpdateBillStatusRequest(BaseModel):
    status: BillStatus


class BillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    name: str
    amount: float
    type: BillType
    cadence: BillCadence
    next_due_date: date
    account_id: uuid.UUID | None
    category_id: uuid.UUID | None
    status: BillStatus
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class CompleteBillRequest(BaseModel):
    amount: float = Field(..., gt=0)


class BillCompletionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bill_id: uuid.UUID
    cycle_due_date: date
    amount: float
    transaction_id: uuid.UUID
    completed_by_user_id: uuid.UUID
    completed_at: datetime


class CreateBillReminderRequest(BaseModel):
    bill_offset: BillReminderOffset
    remind_time: time


class UpdateBillReminderRequest(BaseModel):
    is_enabled: bool


class BillReminderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bill_id: uuid.UUID
    bill_offset: BillReminderOffset
    remind_time: time
    is_enabled: bool
    queued_at: datetime | None
    created_at: datetime
