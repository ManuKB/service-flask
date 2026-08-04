import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.family_membership import FamilyMembership
from app.models.medicine import Medicine
from app.modules.audit.service import record_event
from app.modules.health.patients.service import authorize_patient


class MedicineError(Exception):
    """Raised for any medicine-domain failure the router should turn into an HTTP error."""


def create_medicine(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    patient_id: uuid.UUID,
    membership: FamilyMembership,
    name: str,
    dosage: str,
    schedule_text: str,
    start_date: date | None,
    end_date: date | None,
    notes: str | None,
) -> Medicine:
    authorize_patient(db, family_id, patient_id, membership)
    medicine = Medicine(
        patient_id=patient_id,
        name=name,
        dosage=dosage,
        schedule_text=schedule_text,
        start_date=start_date,
        end_date=end_date,
        notes=notes,
        created_by_user_id=user_id,
    )
    db.add(medicine)
    db.commit()
    db.refresh(medicine)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=user_id,
        action="medicine.created",
        entity_type="Medicine",
        entity_id=medicine.id,
        new_value={"patient_id": str(patient_id), "name": name},
        source_service="health",
    )
    return medicine


def _get_medicine_row(db: Session, patient_id: uuid.UUID, medicine_id: uuid.UUID) -> Medicine:
    medicine = db.get(Medicine, medicine_id)
    if not medicine or medicine.patient_id != patient_id:
        raise MedicineError("Medicine not found")
    return medicine


def get_medicine(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    patient_id: uuid.UUID,
    medicine_id: uuid.UUID,
    membership: FamilyMembership,
) -> Medicine:
    authorize_patient(db, family_id, patient_id, membership)
    medicine = _get_medicine_row(db, patient_id, medicine_id)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=user_id,
        action="medicine.viewed",
        entity_type="Medicine",
        entity_id=medicine.id,
        source_service="health",
    )
    return medicine


def list_medicines(
    db: Session, family_id: uuid.UUID, patient_id: uuid.UUID, membership: FamilyMembership
) -> list[Medicine]:
    authorize_patient(db, family_id, patient_id, membership)
    result = db.scalars(
        select(Medicine).where(Medicine.patient_id == patient_id).order_by(Medicine.created_at.desc())
    )
    return list(result)


def update_medicine(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    patient_id: uuid.UUID,
    medicine_id: uuid.UUID,
    membership: FamilyMembership,
    *,
    name: str | None = None,
    dosage: str | None = None,
    schedule_text: str | None = None,
    start_date: date | None = None,
    clear_start_date: bool = False,
    end_date: date | None = None,
    clear_end_date: bool = False,
    notes: str | None = None,
    clear_notes: bool = False,
) -> Medicine:
    authorize_patient(db, family_id, patient_id, membership)
    medicine = _get_medicine_row(db, patient_id, medicine_id)

    if name is not None:
        medicine.name = name
    if dosage is not None:
        medicine.dosage = dosage
    if schedule_text is not None:
        medicine.schedule_text = schedule_text
    if clear_start_date:
        medicine.start_date = None
    elif start_date is not None:
        medicine.start_date = start_date
    if clear_end_date:
        medicine.end_date = None
    elif end_date is not None:
        medicine.end_date = end_date
    if clear_notes:
        medicine.notes = None
    elif notes is not None:
        medicine.notes = notes

    db.commit()
    db.refresh(medicine)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=user_id,
        action="medicine.updated",
        entity_type="Medicine",
        entity_id=medicine.id,
        source_service="health",
    )
    return medicine


def delete_medicine(
    db: Session, family_id: uuid.UUID, patient_id: uuid.UUID, medicine_id: uuid.UUID, membership: FamilyMembership
) -> None:
    authorize_patient(db, family_id, patient_id, membership)
    medicine = _get_medicine_row(db, patient_id, medicine_id)
    db.delete(medicine)
    db.commit()
