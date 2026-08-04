import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateMedicineRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    dosage: str = Field(min_length=1, max_length=255)
    schedule_text: str = Field(min_length=1, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = None


class UpdateMedicineRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    dosage: str | None = Field(default=None, min_length=1, max_length=255)
    schedule_text: str | None = Field(default=None, min_length=1, max_length=255)
    start_date: date | None = None
    clear_start_date: bool = False
    end_date: date | None = None
    clear_end_date: bool = False
    notes: str | None = None
    clear_notes: bool = False


class MedicineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    name: str
    dosage: str
    schedule_text: str
    start_date: date | None
    end_date: date | None
    notes: str | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
