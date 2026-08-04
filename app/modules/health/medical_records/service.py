import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.family_membership import FamilyMembership
from app.models.medical_record import MedicalRecord
from app.modules.audit.service import record_event
from app.modules.health.attachments import validate_attachment_url
from app.modules.health.enums import MedicalRecordType
from app.modules.health.patients.service import authorize_patient


class MedicalRecordError(Exception):
    """Raised for any medical-record-domain failure the router should turn into an HTTP error."""


def create_record(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    patient_id: uuid.UUID,
    membership: FamilyMembership,
    record_type: MedicalRecordType,
    record_date: date,
    notes: str | None,
    attachment_url: str | None,
) -> MedicalRecord:
    authorize_patient(db, family_id, patient_id, membership)
    validate_attachment_url(attachment_url)

    record = MedicalRecord(
        patient_id=patient_id,
        record_type=record_type,
        record_date=record_date,
        notes=notes,
        attachment_url=attachment_url,
        created_by_user_id=user_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=user_id,
        action="medical_record.created",
        entity_type="MedicalRecord",
        entity_id=record.id,
        new_value={"patient_id": str(patient_id), "record_type": record_type.value},
        source_service="health",
    )
    return record


def _get_record_row(db: Session, patient_id: uuid.UUID, record_id: uuid.UUID) -> MedicalRecord:
    record = db.get(MedicalRecord, record_id)
    if not record or record.patient_id != patient_id:
        raise MedicalRecordError("Medical record not found")
    return record


def get_record(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    patient_id: uuid.UUID,
    record_id: uuid.UUID,
    membership: FamilyMembership,
) -> MedicalRecord:
    authorize_patient(db, family_id, patient_id, membership)
    record = _get_record_row(db, patient_id, record_id)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=user_id,
        action="medical_record.viewed",
        entity_type="MedicalRecord",
        entity_id=record.id,
        source_service="health",
    )
    return record


def list_records(
    db: Session,
    family_id: uuid.UUID,
    patient_id: uuid.UUID,
    membership: FamilyMembership,
    record_type: MedicalRecordType | None = None,
) -> list[MedicalRecord]:
    authorize_patient(db, family_id, patient_id, membership)
    query = select(MedicalRecord).where(MedicalRecord.patient_id == patient_id)
    if record_type is not None:
        query = query.where(MedicalRecord.record_type == record_type)
    result = db.scalars(query.order_by(MedicalRecord.record_date.desc()))
    return list(result)


def update_record(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    patient_id: uuid.UUID,
    record_id: uuid.UUID,
    membership: FamilyMembership,
    *,
    record_type: MedicalRecordType | None = None,
    record_date: date | None = None,
    notes: str | None = None,
    clear_notes: bool = False,
    attachment_url: str | None = None,
    clear_attachment: bool = False,
) -> MedicalRecord:
    authorize_patient(db, family_id, patient_id, membership)
    record = _get_record_row(db, patient_id, record_id)

    if record_type is not None:
        record.record_type = record_type
    if record_date is not None:
        record.record_date = record_date
    if clear_notes:
        record.notes = None
    elif notes is not None:
        record.notes = notes
    if clear_attachment:
        record.attachment_url = None
    elif attachment_url is not None:
        validate_attachment_url(attachment_url)
        record.attachment_url = attachment_url

    db.commit()
    db.refresh(record)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=user_id,
        action="medical_record.updated",
        entity_type="MedicalRecord",
        entity_id=record.id,
        source_service="health",
    )
    return record


def delete_record(
    db: Session, family_id: uuid.UUID, patient_id: uuid.UUID, record_id: uuid.UUID, membership: FamilyMembership
) -> None:
    authorize_patient(db, family_id, patient_id, membership)
    record = _get_record_row(db, patient_id, record_id)
    db.delete(record)
    db.commit()
