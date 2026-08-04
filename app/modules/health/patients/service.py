import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.family_membership import FamilyMembership
from app.models.patient import Patient
from app.modules.audit.service import record_event
from app.modules.health.access import FULL_ACCESS_ROLES, check_patient_access


class PatientError(Exception):
    """Raised for any patient-domain failure the router should turn into an HTTP error."""


def _validate_linked_user(db: Session, family_id: uuid.UUID, linked_user_id: uuid.UUID) -> None:
    membership = db.scalar(
        select(FamilyMembership).where(
            FamilyMembership.family_id == family_id, FamilyMembership.user_id == linked_user_id
        )
    )
    if not membership:
        raise PatientError("Selected member is not part of this family")


def create_patient(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    linked_user_id: uuid.UUID,
    date_of_birth: date | None,
    relationship_label: str | None,
    notes: str | None,
) -> Patient:
    _validate_linked_user(db, family_id, linked_user_id)

    patient = Patient(
        family_id=family_id,
        name=name,
        linked_user_id=linked_user_id,
        date_of_birth=date_of_birth,
        relationship_label=relationship_label,
        notes=notes,
        created_by_user_id=user_id,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=user_id,
        action="patient.created",
        entity_type="Patient",
        entity_id=patient.id,
        new_value={"name": name},
        source_service="health",
    )
    return patient


def _get_patient_row(db: Session, family_id: uuid.UUID, patient_id: uuid.UUID) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient or patient.family_id != family_id:
        raise PatientError("Patient not found")
    return patient


def get_patient(
    db: Session, family_id: uuid.UUID, patient_id: uuid.UUID, membership: FamilyMembership, *, user_id: uuid.UUID
) -> Patient:
    patient = _get_patient_row(db, family_id, patient_id)
    check_patient_access(membership, patient)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=user_id,
        action="patient.viewed",
        entity_type="Patient",
        entity_id=patient.id,
        source_service="health",
    )
    return patient


def list_patients(db: Session, family_id: uuid.UUID, membership: FamilyMembership) -> list[Patient]:
    result = db.scalars(select(Patient).where(Patient.family_id == family_id).order_by(Patient.name))
    patients = list(result)
    # Consent filtering applies to listing too - a restricted role must never
    # see another patient's name/existence in the list, not just be blocked
    # from the detail view.
    if membership.role in FULL_ACCESS_ROLES:
        return patients
    return [p for p in patients if p.linked_user_id == membership.user_id]


def update_patient(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    patient_id: uuid.UUID,
    membership: FamilyMembership,
    *,
    name: str | None = None,
    date_of_birth: date | None = None,
    clear_date_of_birth: bool = False,
    relationship_label: str | None = None,
    clear_relationship_label: bool = False,
    notes: str | None = None,
    clear_notes: bool = False,
) -> Patient:
    patient = _get_patient_row(db, family_id, patient_id)
    check_patient_access(membership, patient)

    if name is not None:
        patient.name = name
    if clear_date_of_birth:
        patient.date_of_birth = None
    elif date_of_birth is not None:
        patient.date_of_birth = date_of_birth
    if clear_relationship_label:
        patient.relationship_label = None
    elif relationship_label is not None:
        patient.relationship_label = relationship_label
    if clear_notes:
        patient.notes = None
    elif notes is not None:
        patient.notes = notes

    db.commit()
    db.refresh(patient)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=user_id,
        action="patient.updated",
        entity_type="Patient",
        entity_id=patient.id,
        source_service="health",
    )
    return patient


def authorize_patient(
    db: Session, family_id: uuid.UUID, patient_id: uuid.UUID, membership: FamilyMembership
) -> Patient:
    """Shared helper for patient-scoped sub-resources (medical records,
    medicines, appointments): resolves the patient and enforces the same
    consent check, without recording a 'patient.viewed' audit event of its
    own - the caller records its own more specific action."""
    patient = _get_patient_row(db, family_id, patient_id)
    check_patient_access(membership, patient)
    return patient
