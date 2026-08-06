import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.budget import Budget
from app.models.category import Category
from app.models.recurring_bill import RecurringBill
from app.models.transaction import Transaction
from app.modules.finance.budgets.service import actual_spend, list_budgets_with_status
from app.modules.finance.dateutils import month_range, year_range
from app.modules.finance.enums import BillStatus, CategoryType


def _sum_by_type(db: Session, family_id: uuid.UUID, type_: CategoryType, start: date, end: date) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.family_id == family_id,
            Transaction.type == type_,
            Transaction.occurred_on >= start,
            Transaction.occurred_on < end,
        )
    )
    return Decimal(total)


def _flatten_month_budget_row(family_id: uuid.UUID, row: dict) -> dict:
    budget: Budget = row["budget"]
    return {
        "id": budget.id,
        "family_id": family_id,
        "category_id": budget.category_id,
        "category_name": row["category_name"],
        "month": budget.month,
        "limit_amount": row["budget"].limit_amount,
        "actual_spend": row["actual_spend"],
        "is_over_limit": row["is_over_limit"],
    }


def _budget_statuses_for_year(db: Session, family_id: uuid.UUID, year_start: date) -> list[dict]:
    """Aggregates every monthly budget set within the year into one row per
    category - summed limit and summed actual spend across the months that
    have a budget - since a Budget row is inherently month-scoped and there's
    no separate yearly-budget concept to read from."""
    start, end = year_range(year_start)
    result = db.execute(
        select(Budget, Category.name)
        .join(Category, Category.id == Budget.category_id)
        .where(Budget.family_id == family_id, Budget.month >= start, Budget.month < end)
        .order_by(Category.name, Budget.month)
    )

    aggregated: dict[uuid.UUID, dict] = {}
    for budget, category_name in result.all():
        spent = actual_spend(db, family_id, budget.category_id, budget.month)
        bucket = aggregated.setdefault(
            budget.category_id,
            {
                "id": budget.id,
                "family_id": family_id,
                "category_id": budget.category_id,
                "category_name": category_name,
                "month": start,
                "limit_amount": Decimal(0),
                "actual_spend": Decimal(0),
            },
        )
        bucket["limit_amount"] += budget.limit_amount
        bucket["actual_spend"] += spent

    statuses = list(aggregated.values())
    for status in statuses:
        status["is_over_limit"] = status["actual_spend"] > status["limit_amount"]
    statuses.sort(key=lambda s: s["category_name"])
    return statuses


def _upcoming_bills(db: Session, family_id: uuid.UUID) -> list[RecurringBill]:
    """Active bills due within the next 15 days - overdue bills (due date
    already in the past) are included too, so the owner is never blindsided
    by a bill that silently aged out of the window."""
    cutoff = date.today() + timedelta(days=15)
    result = db.scalars(
        select(RecurringBill)
        .where(
            RecurringBill.family_id == family_id,
            RecurringBill.status == BillStatus.ACTIVE,
            RecurringBill.next_due_date <= cutoff,
        )
        .order_by(RecurringBill.next_due_date)
    )
    return list(result)


def get_overview(db: Session, family_id: uuid.UUID, month: date) -> dict:
    start, end = month_range(month)

    income_total = _sum_by_type(db, family_id, CategoryType.INCOME, start, end)
    expense_total = _sum_by_type(db, family_id, CategoryType.EXPENSE, start, end)

    budget_rows = list_budgets_with_status(db, family_id, start)

    return {
        "month": start,
        "income_total": income_total,
        "expense_total": expense_total,
        "net_total": income_total - expense_total,
        "budget_statuses": [_flatten_month_budget_row(family_id, row) for row in budget_rows],
        "upcoming_bills": _upcoming_bills(db, family_id),
    }


def get_overview_for_year(db: Session, family_id: uuid.UUID, year: date) -> dict:
    start, end = year_range(year)

    income_total = _sum_by_type(db, family_id, CategoryType.INCOME, start, end)
    expense_total = _sum_by_type(db, family_id, CategoryType.EXPENSE, start, end)

    return {
        "month": start,
        "income_total": income_total,
        "expense_total": expense_total,
        "net_total": income_total - expense_total,
        "budget_statuses": _budget_statuses_for_year(db, family_id, start),
        "upcoming_bills": _upcoming_bills(db, family_id),
    }
