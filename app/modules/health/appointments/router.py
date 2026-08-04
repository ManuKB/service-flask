import uuid

from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AppError
from app.core.responses import envelope, envelope_list, no_content
from app.modules.health.access import HealthAccessError
from app.modules.health.appointments import service
from app.modules.health.patients.service import PatientError
from app.modules.permissions.rbac import require_active_member
from app.schemas.health.appointments import AppointmentResponse, CreateAppointmentRequest, UpdateAppointmentRequest

bp = Blueprint(
    "health_appointments",
    __name__,
    url_prefix="/families/<uuid:family_id>/health/patients/<uuid:patient_id>/appointments",
)


def _to_app_error(exc: Exception) -> AppError:
    if isinstance(exc, HealthAccessError):
        return AppError(status.HTTP_403_FORBIDDEN, str(exc))
    return AppError(status.HTTP_404_NOT_FOUND, str(exc))


@bp.post("")
def create_appointment(family_id: uuid.UUID, patient_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    membership = require_active_member(db, family_id, user_id)
    payload = CreateAppointmentRequest(**request.get_json(force=True))
    try:
        appointment = service.create_appointment(
            db,
            family_id,
            user_id,
            patient_id,
            membership,
            payload.doctor_id,
            payload.scheduled_at,
            payload.notes,
            payload.create_calendar_event,
            payload.reminder_enabled,
        )
    except (HealthAccessError, PatientError, service.AppointmentError) as exc:
        raise _to_app_error(exc) from exc
    return envelope(AppointmentResponse.model_validate(appointment), status.HTTP_201_CREATED)


@bp.get("")
def list_appointments(family_id: uuid.UUID, patient_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    membership = require_active_member(db, family_id, user_id)
    try:
        appointments = service.list_appointments(db, family_id, patient_id, membership)
    except (HealthAccessError, PatientError) as exc:
        raise _to_app_error(exc) from exc
    return envelope_list([AppointmentResponse.model_validate(a) for a in appointments])


@bp.get("/<uuid:appointment_id>")
def get_appointment(family_id: uuid.UUID, patient_id: uuid.UUID, appointment_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    membership = require_active_member(db, family_id, user_id)
    try:
        appointment = service.get_appointment(db, family_id, user_id, patient_id, appointment_id, membership)
    except (HealthAccessError, PatientError, service.AppointmentError) as exc:
        raise _to_app_error(exc) from exc
    return envelope(AppointmentResponse.model_validate(appointment))


@bp.patch("/<uuid:appointment_id>")
def update_appointment(family_id: uuid.UUID, patient_id: uuid.UUID, appointment_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    membership = require_active_member(db, family_id, user_id)
    payload = UpdateAppointmentRequest(**request.get_json(force=True))
    try:
        appointment = service.update_appointment(
            db,
            family_id,
            user_id,
            patient_id,
            appointment_id,
            membership,
            doctor_id=payload.doctor_id,
            clear_doctor=payload.clear_doctor,
            scheduled_at=payload.scheduled_at,
            notes=payload.notes,
            clear_notes=payload.clear_notes,
            reminder_enabled=payload.reminder_enabled,
        )
    except (HealthAccessError, PatientError, service.AppointmentError) as exc:
        raise _to_app_error(exc) from exc
    return envelope(AppointmentResponse.model_validate(appointment))


@bp.delete("/<uuid:appointment_id>")
def delete_appointment(family_id: uuid.UUID, patient_id: uuid.UUID, appointment_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    membership = require_active_member(db, family_id, user_id)
    try:
        service.delete_appointment(db, family_id, patient_id, appointment_id, membership)
    except (HealthAccessError, PatientError, service.AppointmentError) as exc:
        raise _to_app_error(exc) from exc
    return no_content()
