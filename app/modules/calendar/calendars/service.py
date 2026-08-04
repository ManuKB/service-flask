import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.calendar import Calendar

DEFAULT_CALENDAR_NAME = "Family Calendar"


def ensure_default_calendar(db: Session, family_id: uuid.UUID, owner_user_id: uuid.UUID) -> Calendar:
    """Every family has a default shared calendar (S3-01). Created lazily and
    idempotently the first time a family's calendars are touched, so it works
    both for brand-new families and ones that existed before this feature."""
    existing = db.scalar(
        select(Calendar).where(Calendar.family_id == family_id, Calendar.is_default.is_(True))
    )
    if existing:
        return existing

    calendar = Calendar(
        family_id=family_id, name=DEFAULT_CALENDAR_NAME, is_default=True, created_by_user_id=owner_user_id
    )
    db.add(calendar)
    db.commit()
    db.refresh(calendar)
    return calendar


def list_calendars(db: Session, family_id: uuid.UUID, user_id: uuid.UUID) -> list[Calendar]:
    ensure_default_calendar(db, family_id, user_id)
    result = db.scalars(
        select(Calendar).where(Calendar.family_id == family_id).order_by(Calendar.is_default.desc(), Calendar.name)
    )
    return list(result)


def create_calendar(db: Session, family_id: uuid.UUID, user_id: uuid.UUID, name: str) -> Calendar:
    calendar = Calendar(family_id=family_id, name=name, is_default=False, created_by_user_id=user_id)
    db.add(calendar)
    db.commit()
    db.refresh(calendar)
    return calendar
