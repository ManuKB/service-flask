import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.finance.enums import CategoryType


class CreateTransactionRequest(BaseModel):
    account_id: uuid.UUID
    category_id: uuid.UUID
    type: CategoryType
    amount: float = Field(gt=0)
    occurred_on: date
    notes: str | None = None
    attachment_url: str | None = None


class UpdateTransactionRequest(BaseModel):
    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    type: CategoryType | None = None
    amount: float | None = Field(default=None, gt=0)
    occurred_on: date | None = None
    notes: str | None = None
    attachment_url: str | None = None


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    account_id: uuid.UUID
    category_id: uuid.UUID
    type: CategoryType
    amount: float
    occurred_on: date
    notes: str | None
    attachment_url: str | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
