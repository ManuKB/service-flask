import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateShoppingListRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class RenameShoppingListRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ShoppingListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    name: str
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class CreateShoppingItemRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    quantity: str | None = Field(default=None, max_length=50)
    notes: str | None = None
    store: str | None = Field(default=None, max_length=255)


class UpdateShoppingItemRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    quantity: str | None = None
    clear_quantity: bool = False
    notes: str | None = None
    clear_notes: bool = False
    store: str | None = None
    clear_store: bool = False


class ShoppingItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    list_id: uuid.UUID
    name: str
    quantity: str | None
    notes: str | None
    store: str | None
    is_purchased: bool
    purchased_by_user_id: uuid.UUID | None
    purchased_at: datetime | None
    transaction_id: uuid.UUID | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PurchaseItemRequest(BaseModel):
    """All fields optional - a plain "got it" purchase records no expense.
    If an amount is given, account_id and category_id become required so an
    expense Transaction can be recorded alongside the purchase."""

    amount: float | None = Field(default=None, gt=0)
    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    occurred_on: date | None = None
