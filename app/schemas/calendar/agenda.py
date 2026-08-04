import uuid
from datetime import date, datetime

from pydantic import BaseModel


class AgendaOccurrenceResponse(BaseModel):
    event_id: uuid.UUID
    calendar_id: uuid.UUID
    title: str
    description: str | None
    location: str | None
    occurrence_date: date
    start_at: datetime
    end_at: datetime
    is_recurring: bool
    is_exception: bool
    is_completed: bool
    participant_user_ids: list[uuid.UUID]


class AgendaResponse(BaseModel):
    start: date
    end: date
    occurrences: list[AgendaOccurrenceResponse]
