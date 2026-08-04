import uuid

from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AppError
from app.core.responses import envelope, envelope_list
from app.modules.families import service
from app.modules.permissions.rbac import require_active_member, require_owner
from app.schemas.family import (
    AddMemberRequest,
    AddMemberResponse,
    ChangeRoleRequest,
    CreateFamilyRequest,
    FamilyResponse,
    MembershipResponse,
)

bp = Blueprint("families", __name__, url_prefix="/families")


@bp.post("")
def create_family():
    user_id = get_current_user_id()
    db = get_db()
    payload = CreateFamilyRequest(**request.get_json(force=True))
    try:
        family = service.create_family(db, user_id, payload.name)
    except service.FamilyError as exc:
        raise AppError(status.HTTP_409_CONFLICT, str(exc)) from exc
    return envelope(FamilyResponse.model_validate(family), status.HTTP_201_CREATED)


@bp.get("/me")
def get_my_family():
    user_id = get_current_user_id()
    db = get_db()
    family = service.get_family_for_user(db, user_id)
    if not family:
        raise AppError(status.HTTP_404_NOT_FOUND, "No family found for this user")
    return envelope(FamilyResponse.model_validate(family))


@bp.get("/<uuid:family_id>/members")
def get_members(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    memberships = service.list_members(db, family_id)
    dicts = service.to_membership_dicts(db, memberships)
    return envelope_list([MembershipResponse.model_validate(d) for d in dicts])


@bp.patch("/<uuid:family_id>/members/<uuid:member_id>/role")
def change_role(family_id: uuid.UUID, member_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    owner_membership = require_owner(db, family_id, user_id)
    payload = ChangeRoleRequest(**request.get_json(force=True))
    try:
        membership = service.change_member_role(db, family_id, member_id, payload.role, owner_membership.user_id)
    except service.FamilyError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    membership_dict = service.to_membership_dict(db, membership)
    return envelope(MembershipResponse.model_validate(membership_dict))


@bp.post("/<uuid:family_id>/members")
def add_member(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    owner_membership = require_owner(db, family_id, user_id)
    payload = AddMemberRequest(**request.get_json(force=True))
    try:
        membership, created_new_account = service.add_member_by_email(
            db, family_id, owner_membership.user_id, payload.email, payload.role, payload.name
        )
    except service.FamilyError as exc:
        raise AppError(status.HTTP_409_CONFLICT, str(exc)) from exc
    membership_dict = service.to_membership_dict(db, membership)
    return envelope(
        AddMemberResponse(membership=MembershipResponse.model_validate(membership_dict), created_new_account=created_new_account),
        status.HTTP_201_CREATED,
    )
