import uuid

from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AppError
from app.core.responses import envelope, envelope_list, no_content
from app.modules.finance.bills import service
from app.modules.permissions.rbac import require_active_member
from app.schemas.finance.bills import (
    BillCompletionResponse,
    BillReminderResponse,
    BillResponse,
    CompleteBillRequest,
    CreateBillReminderRequest,
    CreateBillRequest,
    UpdateBillReminderRequest,
    UpdateBillStatusRequest,
)

bp = Blueprint("finance_bills", __name__, url_prefix="/families/<uuid:family_id>/finance/bills")


@bp.post("")
def create_bill(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = CreateBillRequest(**request.get_json(force=True))
    bill = service.create_bill(
        db,
        family_id,
        user_id,
        payload.name,
        payload.amount,
        payload.type,
        payload.cadence,
        payload.next_due_date,
        payload.account_id,
        payload.category_id,
    )
    return envelope(BillResponse.model_validate(bill), status.HTTP_201_CREATED)


@bp.get("")
def list_bills(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    bills = service.list_bills(db, family_id)
    return envelope_list([BillResponse.model_validate(b) for b in bills])


@bp.patch("/<uuid:bill_id>")
def update_bill_status(family_id: uuid.UUID, bill_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = UpdateBillStatusRequest(**request.get_json(force=True))
    try:
        bill = service.set_bill_status(db, family_id, bill_id, payload.status)
    except service.BillError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(BillResponse.model_validate(bill))


@bp.delete("/<uuid:bill_id>")
def delete_bill(family_id: uuid.UUID, bill_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    try:
        service.delete_bill(db, family_id, bill_id)
    except service.BillError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return no_content()


@bp.post("/<uuid:bill_id>/remind")
def remind_bill(family_id: uuid.UUID, bill_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    try:
        service.send_reminder(db, family_id, bill_id)
    except service.BillError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return no_content()


@bp.post("/<uuid:bill_id>/reminders")
def create_bill_reminder(family_id: uuid.UUID, bill_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = CreateBillReminderRequest(**request.get_json(force=True))
    try:
        reminder = service.create_bill_reminder(db, family_id, user_id, bill_id, payload.bill_offset, payload.remind_time)
    except service.BillError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(BillReminderResponse.model_validate(reminder), status.HTTP_201_CREATED)


@bp.get("/<uuid:bill_id>/reminders")
def list_bill_reminders(family_id: uuid.UUID, bill_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    try:
        reminders = service.list_bill_reminders(db, family_id, bill_id)
    except service.BillError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope_list([BillReminderResponse.model_validate(r) for r in reminders])


@bp.patch("/<uuid:bill_id>/reminders/<uuid:reminder_id>")
def update_bill_reminder(family_id: uuid.UUID, bill_id: uuid.UUID, reminder_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = UpdateBillReminderRequest(**request.get_json(force=True))
    try:
        reminder = service.set_bill_reminder_enabled(db, family_id, bill_id, reminder_id, payload.is_enabled)
    except service.BillError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(BillReminderResponse.model_validate(reminder))


@bp.post("/<uuid:bill_id>/complete")
def complete_bill(family_id: uuid.UUID, bill_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = CompleteBillRequest(**request.get_json(force=True))
    try:
        completion = service.complete_bill(db, family_id, user_id, bill_id, payload.amount)
    except service.BillError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return envelope(BillCompletionResponse.model_validate(completion), status.HTTP_201_CREATED)


@bp.get("/<uuid:bill_id>/completions")
def list_bill_completions(family_id: uuid.UUID, bill_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    try:
        completions = service.list_bill_completions(db, family_id, bill_id)
    except service.BillError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope_list([BillCompletionResponse.model_validate(c) for c in completions])


@bp.post("/<uuid:bill_id>/completions/<uuid:completion_id>/undo")
def undo_bill_completion(family_id: uuid.UUID, bill_id: uuid.UUID, completion_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    try:
        service.undo_bill_completion(db, family_id, user_id, bill_id, completion_id)
    except service.BillError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return no_content()
