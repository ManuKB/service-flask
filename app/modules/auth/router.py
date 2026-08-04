from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.responses import envelope, no_content
from app.modules.auth import service
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    PasswordSetupPreviewResponse,
    RefreshRequest,
    RegisterRequest,
    SetPasswordRequest,
    TokenResponse,
    UserResponse,
)

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.post("/register")
def register():
    payload = RegisterRequest(**request.get_json(force=True))
    db = get_db()
    try:
        user = service.register_user(db, payload.email, payload.password, payload.name)
    except service.AuthError as exc:
        raise AppError(status.HTTP_409_CONFLICT, str(exc)) from exc
    return envelope(UserResponse.model_validate(user), status.HTTP_201_CREATED)


@bp.post("/login")
def login():
    payload = LoginRequest(**request.get_json(force=True))
    db = get_db()
    try:
        user = service.authenticate_user(db, payload.email, payload.password)
        access_token, refresh_token = service.issue_tokens(db, user)
    except service.AuthError as exc:
        raise AppError(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    return envelope(TokenResponse(access_token=access_token, refresh_token=refresh_token))


@bp.post("/refresh")
def refresh():
    payload = RefreshRequest(**request.get_json(force=True))
    db = get_db()
    try:
        access_token, refresh_token = service.rotate_refresh_token(db, payload.refresh_token)
    except service.AuthError as exc:
        raise AppError(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    return envelope(TokenResponse(access_token=access_token, refresh_token=refresh_token))


@bp.post("/logout")
def logout():
    payload = LogoutRequest(**request.get_json(force=True))
    service.revoke_refresh_token(get_db(), payload.refresh_token)
    return no_content()


@bp.get("/password-setup/<token>")
def preview_password_setup(token: str):
    db = get_db()
    try:
        user = service.preview_password_setup(db, token)
    except service.AuthError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(PasswordSetupPreviewResponse(email=user.email))


@bp.post("/set-password")
def set_password():
    payload = SetPasswordRequest(**request.get_json(force=True))
    db = get_db()
    try:
        service.set_password(db, payload.token, payload.password)
    except service.AuthError as exc:
        raise AppError(status.HTTP_409_CONFLICT, str(exc)) from exc
    return no_content()
