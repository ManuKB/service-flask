import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.finance.enums import AccountType


class CreateAccountRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: AccountType


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    name: str
    type: AccountType
    created_by_user_id: uuid.UUID
    created_at: datetime
