import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateDoctorRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    specialty: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = None


class UpdateDoctorRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    specialty: str | None = None
    clear_specialty: bool = False
    phone: str | None = None
    clear_phone: bool = False
    notes: str | None = None
    clear_notes: bool = False


class DoctorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    name: str
    specialty: str | None
    phone: str | None
    notes: str | None
    created_by_user_id: uuid.UUID
    created_at: datetime
