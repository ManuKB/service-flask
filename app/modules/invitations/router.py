from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AppError
from app.core.responses import envelope
from app.modules.invitations import service
from app.modules.invitations.permissions import require_family_owner
from app.schemas.invitation import (
    AcceptedMembershipResponse,
    CreateInvitationRequest,
    InvitationPreviewResponse,
    InvitationResponse,
)

bp = Blueprint("invitations", __name__)


@bp.post("/families/<uuid:family_id>/invitations")
def create_invitation(family_id):
    user_id = get_current_user_id()
    db = get_db()
    inviter_user_id = require_family_owner(db, family_id, user_id)
    payload = CreateInvitationRequest(**request.get_json(force=True))
    try:
        invitation = service.create_invitation(db, family_id, inviter_user_id, payload.email, payload.role)
    except service.InvitationError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(InvitationResponse.model_validate(invitation), status.HTTP_201_CREATED)


@bp.get("/invitations/<token>")
def preview_invitation(token: str):
    db = get_db()
    try:
        invitation, family = service.preview_invitation(db, token)
    except service.InvitationError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(
        InvitationPreviewResponse(
            family_name=family.name,
            email=invitation.email,
            role=invitation.role,
            status=invitation.status,
            expires_at=invitation.expires_at,
        )
    )


@bp.post("/invitations/<token>/accept")
def accept_invitation(token: str):
    user_id = get_current_user_id()
    db = get_db()
    try:
        membership = service.accept_invitation(db, token, user_id)
    except service.InvitationError as exc:
        raise AppError(status.HTTP_409_CONFLICT, str(exc)) from exc
    return envelope(AcceptedMembershipResponse.model_validate(membership))
