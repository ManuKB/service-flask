from flask import g
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, future=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    """One shared database now means cross-entity references (Family.owner_user_id,
    FamilyMembership.user_id, Invitation.family_id, AuditEvent.actor_user_id, etc.)
    are real foreign keys - SQLite just doesn't enforce them unless told to per connection."""
    if not settings.database_url.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Base(DeclarativeBase):
    pass


def init_models() -> None:
    """Dev convenience only - production schema changes go through Alembic."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Returns the request-scoped SQLAlchemy session. Flask has no built-in
    dependency injection (FastAPI's `Depends(get_db)` counterpart) - instead
    the session is opened in a `before_request` hook and closed in
    `teardown_appcontext` (see app/main.py's create_app()), stashed on
    flask.g so every call within the same request reuses the same session/transaction."""
    return g.db
