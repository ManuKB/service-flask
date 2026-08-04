import uuid

from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AppError
from app.core.responses import envelope, envelope_list, no_content
from app.modules.health.access import HealthAccessError
from app.modules.health.medicines import service
from app.modules.health.patients.service import PatientError
from app.modules.permissions.rbac import require_active_member
from app.schemas.health.medicines import CreateMedicineRequest, MedicineResponse, UpdateMedicineRequest

bp = Blueprint(
    "health_medicines",
    __name__,
    url_prefix="/families/<uuid:family_id>/health/patients/<uuid:patient_id>/medicines",
)


def _to_app_error(exc: Exception) -> AppError:
    if isinstance(exc, HealthAccessError):
        return AppError(status.HTTP_403_FORBIDDEN, str(exc))
    return AppError(status.HTTP_404_NOT_FOUND, str(exc))


@bp.post("")
def create_medicine(family_id: uuid.UUID, patient_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    membership = require_active_member(db, family_id, user_id)
    payload = CreateMedicineRequest(**request.get_json(force=True))
    try:
        medicine = service.create_medicine(
            db,
            family_id,
            user_id,
            patient_id,
            membership,
            payload.name,
            payload.dosage,
            payload.schedule_text,
            payload.start_date,
            payload.end_date,
            payload.notes,
        )
    except (HealthAccessError, PatientError) as exc:
        raise _to_app_error(exc) from exc
    return envelope(MedicineResponse.model_validate(medicine), status.HTTP_201_CREATED)


@bp.get("")
def list_medicines(family_id: uuid.UUID, patient_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    membership = require_active_member(db, family_id, user_id)
    try:
        medicines = service.list_medicines(db, family_id, patient_id, membership)
    except (HealthAccessError, PatientError) as exc:
        raise _to_app_error(exc) from exc
    return envelope_list([MedicineResponse.model_validate(m) for m in medicines])


@bp.get("/<uuid:medicine_id>")
def get_medicine(family_id: uuid.UUID, patient_id: uuid.UUID, medicine_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    membership = require_active_member(db, family_id, user_id)
    try:
        medicine = service.get_medicine(db, family_id, user_id, patient_id, medicine_id, membership)
    except (HealthAccessError, PatientError, service.MedicineError) as exc:
        raise _to_app_error(exc) from exc
    return envelope(MedicineResponse.model_validate(medicine))


@bp.patch("/<uuid:medicine_id>")
def update_medicine(family_id: uuid.UUID, patient_id: uuid.UUID, medicine_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    membership = require_active_member(db, family_id, user_id)
    payload = UpdateMedicineRequest(**request.get_json(force=True))
    try:
        medicine = service.update_medicine(
            db,
            family_id,
            user_id,
            patient_id,
            medicine_id,
            membership,
            name=payload.name,
            dosage=payload.dosage,
            schedule_text=payload.schedule_text,
            start_date=payload.start_date,
            clear_start_date=payload.clear_start_date,
            end_date=payload.end_date,
            clear_end_date=payload.clear_end_date,
            notes=payload.notes,
            clear_notes=payload.clear_notes,
        )
    except (HealthAccessError, PatientError, service.MedicineError) as exc:
        raise _to_app_error(exc) from exc
    return envelope(MedicineResponse.model_validate(medicine))


@bp.delete("/<uuid:medicine_id>")
def delete_medicine(family_id: uuid.UUID, patient_id: uuid.UUID, medicine_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    membership = require_active_member(db, family_id, user_id)
    try:
        service.delete_medicine(db, family_id, patient_id, medicine_id, membership)
    except (HealthAccessError, PatientError, service.MedicineError) as exc:
        raise _to_app_error(exc) from exc
    return no_content()
