import uuid

from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AppError
from app.core.responses import envelope, envelope_list, no_content
from app.modules.finance import dateutils
from app.modules.finance.transactions import service
from app.modules.permissions.rbac import require_active_member
from app.schemas.finance.transactions import CreateTransactionRequest, TransactionResponse, UpdateTransactionRequest

bp = Blueprint("finance_transactions", __name__, url_prefix="/families/<uuid:family_id>/finance/transactions")


@bp.post("")
def create_transaction(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = CreateTransactionRequest(**request.get_json(force=True))
    try:
        transaction = service.create_transaction(
            db,
            family_id,
            user_id,
            payload.account_id,
            payload.category_id,
            payload.type,
            payload.amount,
            payload.occurred_on,
            payload.notes,
            payload.attachment_url,
        )
    except service.TransactionError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return envelope(TransactionResponse.model_validate(transaction), status.HTTP_201_CREATED)


@bp.get("")
def list_transactions(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)

    account_id_raw = request.args.get("account_id")
    category_id_raw = request.args.get("category_id")
    month = request.args.get("month")

    account_id = uuid.UUID(account_id_raw) if account_id_raw else None
    category_id = uuid.UUID(category_id_raw) if category_id_raw else None
    try:
        month_value = dateutils.parse_month(month) if month else None
    except ValueError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    transactions = service.list_transactions(db, family_id, account_id, category_id, month_value)
    return envelope_list([TransactionResponse.model_validate(t) for t in transactions])


@bp.patch("/<uuid:transaction_id>")
def update_transaction(family_id: uuid.UUID, transaction_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = UpdateTransactionRequest(**request.get_json(force=True))
    try:
        transaction = service.update_transaction(
            db,
            family_id,
            user_id,
            transaction_id,
            payload.account_id,
            payload.category_id,
            payload.type,
            payload.amount,
            payload.occurred_on,
            payload.notes,
            payload.attachment_url,
        )
    except service.TransactionError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(TransactionResponse.model_validate(transaction))


@bp.delete("/<uuid:transaction_id>")
def delete_transaction(family_id: uuid.UUID, transaction_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    try:
        service.delete_transaction(db, family_id, user_id, transaction_id)
    except service.TransactionError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return no_content()
