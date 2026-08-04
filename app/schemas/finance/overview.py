from datetime import date

from pydantic import BaseModel

from app.schemas.finance.bills import BillResponse
from app.schemas.finance.budgets import BudgetStatusResponse


class FinanceOverviewResponse(BaseModel):
    month: date
    income_total: float
    expense_total: float
    net_total: float
    budget_statuses: list[BudgetStatusResponse]
    upcoming_bills: list[BillResponse]
