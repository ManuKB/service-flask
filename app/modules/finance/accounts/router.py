import uuid

from flask import Blueprint, request

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.responses import envelope, envelope_list
from app.core import status
from app.modules.finance.accounts import service
from app.modules.permissions.rbac import require_active_member
from app.schemas.finance.accounts import AccountResponse, CreateAccountRequest

bp = Blueprint("finance_accounts", __name__, url_prefix="/families/<uuid:family_id>/finance/accounts")


@bp.post("")
def create_account(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = CreateAccountRequest(**request.get_json(force=True))
    account = service.create_account(db, family_id, user_id, payload.name, payload.type)
    return envelope(AccountResponse.model_validate(account), status.HTTP_201_CREATED)


@bp.get("")
def list_accounts(family_id: uuid.UUID):
    db = get_db()
    user_id = get_current_user_id()
    require_active_member(db, family_id, user_id)
    accounts = service.list_accounts(db, family_id)
    return envelope_list([AccountResponse.model_validate(a) for a in accounts])
