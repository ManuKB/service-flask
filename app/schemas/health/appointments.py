import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CreateAppointmentRequest(BaseModel):
    doctor_id: uuid.UUID | None = None
    scheduled_at: datetime
    notes: str | None = None
    create_calendar_event: bool = False
    reminder_enabled: bool = False


class UpdateAppointmentRequest(BaseModel):
    doctor_id: uuid.UUID | None = None
    clear_doctor: bool = False
    scheduled_at: datetime | None = None
    notes: str | None = None
    clear_notes: bool = False
    reminder_enabled: bool | None = None


class AppointmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID | None
    scheduled_at: datetime
    notes: str | None
    calendar_event_id: uuid.UUID | None
    reminder_enabled: bool
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
