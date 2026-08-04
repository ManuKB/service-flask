import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.password_setup_token import PasswordSetupToken
from app.models.refresh_token import RefreshToken
from app.models.user import User

PASSWORD_SETUP_TTL = timedelta(days=7)


class AuthError(Exception):
    """Raised for any auth failure the router should turn into an HTTP error."""


def register_user(db: Session, email: str, password: str, name: str) -> User:
    existing = db.scalar(select(User).where(User.email == email.lower()))
    if existing:
        raise AuthError("Email is already registered")
    user = User(email=email.lower(), name=name, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def create_user_awaiting_password(db: Session, email: str, name: str) -> User:
    """Creates a real User row for someone an owner is adding directly ("add
    family member") - the account exists (and can be linked to a
    FamilyMembership right away) but its password is an unguessable random
    value until they follow their emailed link and set a real one."""
    user = User(
        email=email.lower(), name=name, hashed_password=hash_password(secrets.token_urlsafe(32)), must_set_password=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def issue_password_setup_token(db: Session, user_id: uuid.UUID) -> str:
    raw_token = secrets.token_urlsafe(32)
    db.add(
        PasswordSetupToken(
            user_id=user_id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(timezone.utc) + PASSWORD_SETUP_TTL,
        )
    )
    db.commit()
    return raw_token


def _get_valid_password_setup_token(db: Session, raw_token: str) -> PasswordSetupToken:
    token_hash = hash_token(raw_token)
    token = db.scalar(select(PasswordSetupToken).where(PasswordSetupToken.token_hash == token_hash))
    if not token:
        raise AuthError("Password setup link not found")
    if token.used_at is not None:
        raise AuthError("This password setup link has already been used")
    expires_at = token.expires_at.replace(tzinfo=timezone.utc) if token.expires_at.tzinfo is None else token.expires_at
    if expires_at < datetime.now(timezone.utc):
        raise AuthError("This password setup link has expired")
    return token


def preview_password_setup(db: Session, raw_token: str) -> User:
    token = _get_valid_password_setup_token(db, raw_token)
    user = db.get(User, token.user_id)
    if not user:
        raise AuthError("Account no longer exists")
    return user


def set_password(db: Session, raw_token: str, new_password: str) -> User:
    token = _get_valid_password_setup_token(db, raw_token)
    user = db.get(User, token.user_id)
    if not user:
        raise AuthError("Account no longer exists")

    user.hashed_password = hash_password(new_password)
    user.must_set_password = False
    token.used_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if not user or not verify_password(password, user.hashed_password):
        raise AuthError("Invalid email or password")
    if not user.is_active:
        raise AuthError("Account is inactive")
    if user.must_set_password:
        raise AuthError("Set your password using the link emailed to you before logging in")
    return user


def issue_tokens(db: Session, user: User) -> tuple[str, str]:
    access_token = create_access_token(str(user.id))
    refresh_token, expires_at = create_refresh_token(str(user.id))
    db.add(RefreshToken(user_id=user.id, token_hash=hash_token(refresh_token), expires_at=expires_at))
    db.commit()
    return access_token, refresh_token


def rotate_refresh_token(db: Session, refresh_token: str) -> tuple[str, str]:
    try:
        payload = decode_token(refresh_token)
    except ValueError as exc:
        raise AuthError("Invalid or expired refresh token") from exc
    if payload.get("type") != "refresh":
        raise AuthError("Invalid token type")

    token_hash = hash_token(refresh_token)
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if not stored or stored.revoked:
        raise AuthError("Refresh token is no longer valid")
    # SQLite doesn't persist tzinfo, so a value read back can be naive even
    # though it was written as UTC - normalize before comparing.
    expires_at = stored.expires_at.replace(tzinfo=timezone.utc) if stored.expires_at.tzinfo is None else stored.expires_at
    if expires_at < datetime.now(timezone.utc):
        raise AuthError("Refresh token is no longer valid")

    user = db.get(User, stored.user_id)
    if not user:
        raise AuthError("User no longer exists")

    stored.revoked = True  # rotate: old refresh token is single-use
    access_token, new_refresh_token = issue_tokens(db, user)
    return access_token, new_refresh_token


def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    token_hash = hash_token(refresh_token)
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if stored:
        stored.revoked = True
        db.commit()
