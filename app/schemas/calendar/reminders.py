import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.calendar.enums import ReminderLeadTime


class CreateReminderRequest(BaseModel):
    lead_time: ReminderLeadTime


class UpdateReminderRequest(BaseModel):
    is_enabled: bool


class ReminderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID
    lead_time: ReminderLeadTime
    is_enabled: bool
    queued_at: datetime | None
    created_at: datetime


class ProcessRemindersResponse(BaseModel):
    queued_reminder_ids: list[uuid.UUID]
