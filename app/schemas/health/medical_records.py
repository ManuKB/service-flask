import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.health.enums import MedicalRecordType


class CreateMedicalRecordRequest(BaseModel):
    record_type: MedicalRecordType
    record_date: date
    notes: str | None = None
    attachment_url: str | None = Field(default=None, max_length=1024)


class UpdateMedicalRecordRequest(BaseModel):
    record_type: MedicalRecordType | None = None
    record_date: date | None = None
    notes: str | None = None
    clear_notes: bool = False
    attachment_url: str | None = Field(default=None, max_length=1024)
    clear_attachment: bool = False


class MedicalRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    record_type: MedicalRecordType
    record_date: date
    notes: str | None
    attachment_url: str | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
