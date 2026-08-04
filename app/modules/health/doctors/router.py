import uuid

from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AppError
from app.core.responses import envelope, envelope_list, no_content
from app.modules.health.doctors import service
from app.modules.permissions.rbac import require_active_member
from app.schemas.health.doctors import CreateDoctorRequest, DoctorResponse, UpdateDoctorRequest

bp = Blueprint("health_doctors", __name__, url_prefix="/families/<uuid:family_id>/health/doctors")


@bp.post("")
def create_doctor(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = CreateDoctorRequest(**request.get_json(force=True))
    doctor = service.create_doctor(db, family_id, user_id, payload.name, payload.specialty, payload.phone, payload.notes)
    return envelope(DoctorResponse.model_validate(doctor), status.HTTP_201_CREATED)


@bp.get("")
def list_doctors(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    doctors = service.list_doctors(db, family_id)
    return envelope_list([DoctorResponse.model_validate(d) for d in doctors])


@bp.patch("/<uuid:doctor_id>")
def update_doctor(family_id: uuid.UUID, doctor_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = UpdateDoctorRequest(**request.get_json(force=True))
    try:
        doctor = service.update_doctor(
            db,
            family_id,
            doctor_id,
            name=payload.name,
            specialty=payload.specialty,
            clear_specialty=payload.clear_specialty,
            phone=payload.phone,
            clear_phone=payload.clear_phone,
            notes=payload.notes,
            clear_notes=payload.clear_notes,
        )
    except service.DoctorError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(DoctorResponse.model_validate(doctor))


@bp.delete("/<uuid:doctor_id>")
def delete_doctor(family_id: uuid.UUID, doctor_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    try:
        service.delete_doctor(db, family_id, doctor_id)
    except service.DoctorError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return no_content()
