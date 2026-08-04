import uuid

from flask import request

from app.core import status
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.security import decode_token
from app.models.user import User

# Flask has no dependency-injection system like FastAPI's `Depends(...)`, so
# these are called explicitly at the top of each route handler instead of
# being declared as parameters - same checks, same order, just invoked by hand.


def _bearer_token() -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise AppError(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return auth_header[len("Bearer ") :]


def get_current_user_id() -> uuid.UUID:
    try:
        payload = decode_token(_bearer_token())
    except ValueError as exc:
        raise AppError(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc
    if payload.get("type") != "access":
        raise AppError(status.HTTP_401_UNAUTHORIZED, "Invalid token type")
    return uuid.UUID(payload["sub"])


def get_current_user() -> User:
    user_id = get_current_user_id()
    db = get_db()
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise AppError(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user
