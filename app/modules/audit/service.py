import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent


def record_event(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    source_service: str,
    family_id: uuid.UUID | None = None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
) -> AuditEvent:
    """Writes an audit row in the caller's own session/transaction - now that
    every module shares one database there's no network hop to fail, so this
    is no longer "best effort": if it raises, the caller's commit rolls back too."""
    event = AuditEvent(
        family_id=family_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        source_service=source_service,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_events_for_family(db: Session, family_id: uuid.UUID) -> list[AuditEvent]:
    result = db.scalars(
        select(AuditEvent).where(AuditEvent.family_id == family_id).order_by(AuditEvent.created_at.desc())
    )
    return list(result)


def list_events_for_entity(db: Session, entity_type: str, entity_id: uuid.UUID) -> list[AuditEvent]:
    """Per-entity activity log (e.g. task activity: assignment and status
    changes) - same table as the family-wide audit log, just filtered down
    to one entity instead of building a parallel activity-log table."""
    result = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id)
        .order_by(AuditEvent.created_at.desc())
    )
    return list(result)
