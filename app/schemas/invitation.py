import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.modules.invitations.statuses import InvitationStatus
from app.modules.permissions.roles import FamilyRole


class CreateInvitationRequest(BaseModel):
    email: EmailStr
    role: FamilyRole = FamilyRole.ADULT


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    email: EmailStr
    role: FamilyRole
    status: InvitationStatus
    invited_by_user_id: uuid.UUID
    expires_at: datetime
    created_at: datetime
    accepted_at: datetime | None


class InvitationPreviewResponse(BaseModel):
    """Public preview shown before accepting - no internal IDs exposed."""

    family_name: str
    email: EmailStr
    role: FamilyRole
    status: InvitationStatus
    expires_at: datetime


class AcceptedMembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    family_id: uuid.UUID
    user_id: uuid.UUID
    role: FamilyRole
    status: str
