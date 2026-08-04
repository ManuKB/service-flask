import uuid

from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AppError
from app.core.responses import envelope, envelope_list
from app.modules.health.access import HealthAccessError
from app.modules.health.patients import service
from app.modules.permissions.rbac import require_active_member
from app.schemas.health.patients import CreatePatientRequest, PatientResponse, UpdatePatientRequest

bp = Blueprint("health_patients", __name__, url_prefix="/families/<uuid:family_id>/health/patients")


@bp.post("")
def create_patient(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = CreatePatientRequest(**request.get_json(force=True))
    try:
        patient = service.create_patient(
            db,
            family_id,
            user_id,
            payload.name,
            payload.linked_user_id,
            payload.date_of_birth,
            payload.relationship_label,
            payload.notes,
        )
    except service.PatientError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return envelope(PatientResponse.model_validate(patient), status.HTTP_201_CREATED)


@bp.get("")
def list_patients(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    membership = require_active_member(db, family_id, user_id)
    patients = service.list_patients(db, family_id, membership)
    return envelope_list([PatientResponse.model_validate(p) for p in patients])


@bp.get("/<uuid:patient_id>")
def get_patient(family_id: uuid.UUID, patient_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    membership = require_active_member(db, family_id, user_id)
    try:
        patient = service.get_patient(db, family_id, patient_id, membership, user_id=user_id)
    except service.PatientError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except HealthAccessError as exc:
        raise AppError(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return envelope(PatientResponse.model_validate(patient))


@bp.patch("/<uuid:patient_id>")
def update_patient(family_id: uuid.UUID, patient_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    membership = require_active_member(db, family_id, user_id)
    payload = UpdatePatientRequest(**request.get_json(force=True))
    try:
        patient = service.update_patient(
            db,
            family_id,
            user_id,
            patient_id,
            membership,
            name=payload.name,
            date_of_birth=payload.date_of_birth,
            clear_date_of_birth=payload.clear_date_of_birth,
            relationship_label=payload.relationship_label,
            clear_relationship_label=payload.clear_relationship_label,
            notes=payload.notes,
            clear_notes=payload.clear_notes,
        )
    except service.PatientError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except HealthAccessError as exc:
        raise AppError(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return envelope(PatientResponse.model_validate(patient))
