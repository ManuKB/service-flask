import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateCalendarRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class CalendarResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    name: str
    is_default: bool
    created_by_user_id: uuid.UUID
    created_at: datetime
