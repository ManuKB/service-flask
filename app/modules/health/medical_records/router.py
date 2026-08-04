import uuid

from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AppError
from app.core.responses import envelope, envelope_list, no_content
from app.modules.health.access import HealthAccessError
from app.modules.health.attachments import AttachmentTypeError
from app.modules.health.enums import MedicalRecordType
from app.modules.health.medical_records import service
from app.modules.health.patients.service import PatientError
from app.modules.permissions.rbac import require_active_member
from app.schemas.health.medical_records import CreateMedicalRecordRequest, MedicalRecordResponse, UpdateMedicalRecordRequest

bp = Blueprint(
    "health_medical_records",
    __name__,
    url_prefix="/families/<uuid:family_id>/health/patients/<uuid:patient_id>/records",
)


def _to_app_error(exc: Exception) -> AppError:
    if isinstance(exc, HealthAccessError):
        return AppError(status.HTTP_403_FORBIDDEN, str(exc))
    if isinstance(exc, (PatientError, service.MedicalRecordError)):
        return AppError(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, AttachmentTypeError):
        return AppError(status.HTTP_400_BAD_REQUEST, str(exc))
    raise exc


@bp.post("")
def create_record(family_id: uuid.UUID, patient_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    membership = require_active_member(db, family_id, user_id)
    payload = CreateMedicalRecordRequest(**request.get_json(force=True))
    try:
        record = service.create_record(
            db,
            family_id,
            user_id,
            patient_id,
            membership,
            payload.record_type,
            payload.record_date,
            payload.notes,
            payload.attachment_url,
        )
    except (HealthAccessError, PatientError, AttachmentTypeError) as exc:
        raise _to_app_error(exc) from exc
    return envelope(MedicalRecordResponse.model_validate(record), status.HTTP_201_CREATED)


@bp.get("")
def list_records(family_id: uuid.UUID, patient_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    membership = require_active_member(db, family_id, user_id)
    record_type_str = request.args.get("record_type")
    record_type = None
    if record_type_str is not None:
        try:
            record_type = MedicalRecordType(record_type_str)
        except ValueError as exc:
            raise AppError(status.HTTP_400_BAD_REQUEST, f"Invalid record_type: {record_type_str}") from exc
    try:
        records = service.list_records(db, family_id, patient_id, membership, record_type)
    except (HealthAccessError, PatientError) as exc:
        raise _to_app_error(exc) from exc
    return envelope_list([MedicalRecordResponse.model_validate(r) for r in records])


@bp.get("/<uuid:record_id>")
def get_record(family_id: uuid.UUID, patient_id: uuid.UUID, record_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    membership = require_active_member(db, family_id, user_id)
    try:
        record = service.get_record(db, family_id, user_id, patient_id, record_id, membership)
    except (HealthAccessError, PatientError, service.MedicalRecordError) as exc:
        raise _to_app_error(exc) from exc
    return envelope(MedicalRecordResponse.model_validate(record))


@bp.patch("/<uuid:record_id>")
def update_record(family_id: uuid.UUID, patient_id: uuid.UUID, record_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    membership = require_active_member(db, family_id, user_id)
    payload = UpdateMedicalRecordRequest(**request.get_json(force=True))
    try:
        record = service.update_record(
            db,
            family_id,
            user_id,
            patient_id,
            record_id,
            membership,
            record_type=payload.record_type,
            record_date=payload.record_date,
            notes=payload.notes,
            clear_notes=payload.clear_notes,
            attachment_url=payload.attachment_url,
            clear_attachment=payload.clear_attachment,
        )
    except (HealthAccessError, PatientError, service.MedicalRecordError, AttachmentTypeError) as exc:
        raise _to_app_error(exc) from exc
    return envelope(MedicalRecordResponse.model_validate(record))


@bp.delete("/<uuid:record_id>")
def delete_record(family_id: uuid.UUID, patient_id: uuid.UUID, record_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    membership = require_active_member(db, family_id, user_id)
    try:
        service.delete_record(db, family_id, patient_id, record_id, membership)
    except (HealthAccessError, PatientError, service.MedicalRecordError) as exc:
        raise _to_app_error(exc) from exc
    return no_content()
