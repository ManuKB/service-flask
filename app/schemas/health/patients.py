import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class CreatePatientRequest(BaseModel):
    # A health profile always represents an existing family member now - no
    # more free-standing "type a name" profiles disconnected from a real
    # account (children join the family for real via the owner-add-member
    # flow, so there's no longer a case for an unlinked profile).
    linked_user_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    date_of_birth: date | None = None
    relationship_label: str | None = Field(default=None, max_length=100)
    notes: str | None = None


class UpdatePatientRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    date_of_birth: date | None = None
    clear_date_of_birth: bool = False
    relationship_label: str | None = None
    clear_relationship_label: bool = False
    notes: str | None = None
    clear_notes: bool = False


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    name: str
    linked_user_id: uuid.UUID | None
    date_of_birth: date | None
    relationship_label: str | None
    notes: str | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
