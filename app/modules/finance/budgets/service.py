import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.budget import Budget
from app.models.category import Category
from app.models.transaction import Transaction
from app.modules.finance.dateutils import month_range
from app.modules.finance.enums import CategoryType


class BudgetError(Exception):
    """Raised for any budget-domain failure the router should turn into an HTTP error."""


def actual_spend(db: Session, family_id: uuid.UUID, category_id: uuid.UUID, month: date) -> Decimal:
    start, end = month_range(month)
    total = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.family_id == family_id,
            Transaction.category_id == category_id,
            Transaction.type == CategoryType.EXPENSE,
            Transaction.occurred_on >= start,
            Transaction.occurred_on < end,
        )
    )
    return Decimal(total)


def create_budget(
    db: Session, family_id: uuid.UUID, category_id: uuid.UUID, month: date, limit_amount: float
) -> Budget:
    category = db.get(Category, category_id)
    if not category or category.family_id != family_id:
        raise BudgetError("Category not found")
    existing = db.scalar(
        select(Budget).where(
            Budget.family_id == family_id, Budget.category_id == category_id, Budget.month == month
        )
    )
    if existing:
        raise BudgetError("A budget already exists for this category and month")

    budget = Budget(family_id=family_id, category_id=category_id, month=month, limit_amount=Decimal(str(limit_amount)))
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


def list_budgets_with_status(db: Session, family_id: uuid.UUID, month: date) -> list[dict]:
    result = db.execute(
        select(Budget, Category.name)
        .join(Category, Category.id == Budget.category_id)
        .where(Budget.family_id == family_id, Budget.month == month)
        .order_by(Category.name)
    )
    statuses = []
    for budget, category_name in result.all():
        spent = actual_spend(db, family_id, budget.category_id, budget.month)
        statuses.append(
            {
                "budget": budget,
                "category_name": category_name,
                "actual_spend": spent,
                "is_over_limit": spent > budget.limit_amount,
            }
        )
    return statuses


def update_budget(db: Session, family_id: uuid.UUID, budget_id: uuid.UUID, limit_amount: float) -> Budget:
    budget = db.get(Budget, budget_id)
    if not budget or budget.family_id != family_id:
        raise BudgetError("Budget not found")
    budget.limit_amount = Decimal(str(limit_amount))
    db.commit()
    db.refresh(budget)
    return budget


def delete_budget(db: Session, family_id: uuid.UUID, budget_id: uuid.UUID) -> None:
    budget = db.get(Budget, budget_id)
    if not budget or budget.family_id != family_id:
        raise BudgetError("Budget not found")
    db.delete(budget)
    db.commit()
