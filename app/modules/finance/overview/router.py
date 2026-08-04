import uuid

from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AppError
from app.core.responses import envelope
from app.modules.finance import dateutils
from app.modules.finance.overview import service
from app.modules.permissions.rbac import require_active_member
from app.schemas.finance.bills import BillResponse
from app.schemas.finance.budgets import BudgetStatusResponse
from app.schemas.finance.overview import FinanceOverviewResponse

bp = Blueprint("finance_overview", __name__, url_prefix="/families/<uuid:family_id>/finance")


@bp.get("/overview")
def get_overview(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)

    month = request.args.get("month")
    year = request.args.get("year")

    if bool(month) == bool(year):
        raise AppError(status.HTTP_400_BAD_REQUEST, "Provide exactly one of month or year")

    try:
        if month:
            overview = service.get_overview(db, family_id, dateutils.parse_month(month))
        else:
            overview = service.get_overview_for_year(db, family_id, dateutils.parse_year(year))
    except ValueError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    response = FinanceOverviewResponse(
        month=overview["month"],
        income_total=float(overview["income_total"]),
        expense_total=float(overview["expense_total"]),
        net_total=float(overview["net_total"]),
        budget_statuses=[BudgetStatusResponse(**row) for row in overview["budget_statuses"]],
        upcoming_bills=[BillResponse.model_validate(bill) for bill in overview["upcoming_bills"]],
    )
    return envelope(response)
