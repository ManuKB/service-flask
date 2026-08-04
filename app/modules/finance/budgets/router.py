import uuid

from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AppError
from app.core.responses import envelope, envelope_list, no_content
from app.modules.finance import dateutils
from app.modules.finance.budgets import service
from app.modules.permissions.rbac import require_active_member
from app.schemas.finance.budgets import BudgetStatusResponse, CreateBudgetRequest, UpdateBudgetRequest

bp = Blueprint("finance_budgets", __name__, url_prefix="/families/<uuid:family_id>/finance/budgets")


def _to_status_response(family_id: uuid.UUID, row: dict) -> BudgetStatusResponse:
    budget = row["budget"]
    return BudgetStatusResponse(
        id=budget.id,
        family_id=family_id,
        category_id=budget.category_id,
        category_name=row["category_name"],
        month=budget.month,
        limit_amount=float(budget.limit_amount),
        actual_spend=float(row["actual_spend"]),
        is_over_limit=row["is_over_limit"],
    )


@bp.post("")
def create_budget(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = CreateBudgetRequest(**request.get_json(force=True))
    month = dateutils.parse_month(payload.month)
    try:
        budget = service.create_budget(db, family_id, payload.category_id, month, payload.limit_amount)
    except service.BudgetError as exc:
        raise AppError(status.HTTP_409_CONFLICT, str(exc)) from exc
    rows = service.list_budgets_with_status(db, family_id, month)
    row = next(r for r in rows if r["budget"].id == budget.id)
    return envelope(_to_status_response(family_id, row), status.HTTP_201_CREATED)


@bp.get("")
def list_budgets(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    month = request.args.get("month")
    if month is None:
        raise AppError(status.HTTP_400_BAD_REQUEST, "month is required")
    try:
        month_value = dateutils.parse_month(month)
    except ValueError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    rows = service.list_budgets_with_status(db, family_id, month_value)
    return envelope_list([_to_status_response(family_id, row) for row in rows])


@bp.patch("/<uuid:budget_id>")
def update_budget(family_id: uuid.UUID, budget_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = UpdateBudgetRequest(**request.get_json(force=True))
    try:
        budget = service.update_budget(db, family_id, budget_id, payload.limit_amount)
    except service.BudgetError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    rows = service.list_budgets_with_status(db, family_id, budget.month)
    row = next(r for r in rows if r["budget"].id == budget.id)
    return envelope(_to_status_response(family_id, row))


@bp.delete("/<uuid:budget_id>")
def delete_budget(family_id: uuid.UUID, budget_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    try:
        service.delete_budget(db, family_id, budget_id)
    except service.BudgetError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return no_content()
