import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.permissions.roles import FamilyRole, MembershipStatus


class CreateFamilyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class FamilyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    owner_user_id: uuid.UUID
    created_at: datetime


class MembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    user_id: uuid.UUID
    role: FamilyRole
    status: MembershipStatus
    joined_at: datetime | None
    # Denormalized from the linked User so every screen can show a real name
    # instead of a truncated id - falls back to email if the user has no name set.
    user_name: str
    user_email: str


class ChangeRoleRequest(BaseModel):
    role: FamilyRole


class AddMemberRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    role: FamilyRole


class AddMemberResponse(BaseModel):
    membership: MembershipResponse
    # True if this email had no existing account - they were emailed a
    # set-your-password link instead of being added instantly and ready to log in.
    created_new_account: bool
