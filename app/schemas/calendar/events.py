import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.calendar.enums import RecurrenceFrequency


class RecurrenceInput(BaseModel):
    frequency: RecurrenceFrequency
    interval: int = Field(default=1, ge=1)
    by_weekday: list[int] | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_weekdays(self):
        if self.by_weekday is not None:
            for day in self.by_weekday:
                if not (0 <= day <= 6):
                    raise ValueError("by_weekday values must be between 0 (Monday) and 6 (Sunday)")
        return self


class RecurrenceInfo(BaseModel):
    frequency: RecurrenceFrequency
    interval: int
    by_weekday: list[int] | None
    end_date: date | None


class CreateEventRequest(BaseModel):
    calendar_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    location: str | None = Field(default=None, max_length=500)
    start_at: datetime
    end_at: datetime
    participant_user_ids: list[uuid.UUID] = Field(default_factory=list)
    recurrence: RecurrenceInput | None = None

    @model_validator(mode="after")
    def validate_time_window(self):
        if self.end_at < self.start_at:
            raise ValueError("end_at cannot precede start_at")
        return self


class UpdateEventRequest(BaseModel):
    """Series-level edit - applies to the base event and therefore every
    non-overridden occurrence. A None field means "leave unchanged"; to
    clear an optional text field send an empty string."""

    calendar_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    location: str | None = Field(default=None, max_length=500)
    start_at: datetime | None = None
    end_at: datetime | None = None
    participant_user_ids: list[uuid.UUID] | None = None
    recurrence: RecurrenceInput | None = None
    clear_recurrence: bool = False


class UpdateOccurrenceRequest(BaseModel):
    """Single-occurrence edit (S3-04): overrides just one date of a
    recurring series without touching the series or other occurrences."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    location: str | None = Field(default=None, max_length=500)
    start_at: datetime | None = None
    end_at: datetime | None = None


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    calendar_id: uuid.UUID
    title: str
    description: str | None
    location: str | None
    start_at: datetime
    end_at: datetime
    recurrence: RecurrenceInfo | None
    participant_user_ids: list[uuid.UUID]
    is_completed: bool
    completed_at: datetime | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
