import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.category import Category
from app.models.transaction import Transaction
from app.modules.audit.service import record_event
from app.modules.finance.dateutils import month_range
from app.modules.finance.enums import CategoryType


class TransactionError(Exception):
    """Raised for any transaction-domain failure the router should turn into an HTTP error."""


def _get_owned_account(db: Session, family_id: uuid.UUID, account_id: uuid.UUID) -> Account:
    account = db.get(Account, account_id)
    if not account or account.family_id != family_id:
        raise TransactionError("Account not found")
    return account


def _get_owned_category(db: Session, family_id: uuid.UUID, category_id: uuid.UUID) -> Category:
    category = db.get(Category, category_id)
    if not category or category.family_id != family_id:
        raise TransactionError("Category not found")
    return category


def create_transaction(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    category_id: uuid.UUID,
    type_: CategoryType,
    amount: float,
    occurred_on: date,
    notes: str | None,
    attachment_url: str | None,
) -> Transaction:
    _get_owned_account(db, family_id, account_id)
    category = _get_owned_category(db, family_id, category_id)
    if category.type != type_:
        raise TransactionError(
            f"Category is a {category.type.value} category and cannot be used for a {type_.value} transaction"
        )

    transaction = Transaction(
        family_id=family_id,
        account_id=account_id,
        category_id=category_id,
        type=type_,
        amount=Decimal(str(amount)),
        occurred_on=occurred_on,
        notes=notes,
        attachment_url=attachment_url,
        created_by_user_id=user_id,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=user_id,
        action="transaction.created",
        entity_type="Transaction",
        entity_id=transaction.id,
        new_value={"amount": str(transaction.amount), "type": type_.value},
        source_service="finance",
    )
    return transaction


def list_transactions(
    db: Session,
    family_id: uuid.UUID,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    month: date | None = None,
) -> list[Transaction]:
    stmt = select(Transaction).where(Transaction.family_id == family_id)
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    if month is not None:
        start, end = month_range(month)
        stmt = stmt.where(Transaction.occurred_on >= start, Transaction.occurred_on < end)
    stmt = stmt.order_by(Transaction.occurred_on.desc(), Transaction.created_at.desc())
    result = db.scalars(stmt)
    return list(result)


def get_transaction(db: Session, family_id: uuid.UUID, transaction_id: uuid.UUID) -> Transaction:
    transaction = db.get(Transaction, transaction_id)
    if not transaction or transaction.family_id != family_id:
        raise TransactionError("Transaction not found")
    return transaction


def update_transaction(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    transaction_id: uuid.UUID,
    account_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    type_: CategoryType | None,
    amount: float | None,
    occurred_on: date | None,
    notes: str | None,
    attachment_url: str | None,
) -> Transaction:
    transaction = get_transaction(db, family_id, transaction_id)
    old_value = {
        "amount": str(transaction.amount),
        "type": transaction.type.value,
        "occurred_on": transaction.occurred_on.isoformat(),
    }

    new_category_id = category_id if category_id is not None else transaction.category_id
    new_type = type_ if type_ is not None else transaction.type

    if account_id is not None:
        _get_owned_account(db, family_id, account_id)
        transaction.account_id = account_id
    if category_id is not None or type_ is not None:
        category = _get_owned_category(db, family_id, new_category_id)
        if category.type != new_type:
            raise TransactionError("Category type does not match transaction type")
    transaction.category_id = new_category_id
    transaction.type = new_type

    if amount is not None:
        transaction.amount = Decimal(str(amount))
    if occurred_on is not None:
        transaction.occurred_on = occurred_on
    if notes is not None:
        transaction.notes = notes
    if attachment_url is not None:
        transaction.attachment_url = attachment_url

    db.commit()
    db.refresh(transaction)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=user_id,
        action="transaction.updated",
        entity_type="Transaction",
        entity_id=transaction.id,
        old_value=old_value,
        new_value={
            "amount": str(transaction.amount),
            "type": transaction.type.value,
            "occurred_on": transaction.occurred_on.isoformat(),
        },
        source_service="finance",
    )
    return transaction


def delete_transaction(
    db: Session, family_id: uuid.UUID, user_id: uuid.UUID, transaction_id: uuid.UUID
) -> None:
    transaction = get_transaction(db, family_id, transaction_id)
    old_value = {"amount": str(transaction.amount), "type": transaction.type.value}
    db.delete(transaction)
    db.commit()

    record_event(
        db,
        family_id=family_id,
        actor_user_id=user_id,
        action="transaction.deleted",
        entity_type="Transaction",
        entity_id=transaction_id,
        old_value=old_value,
        source_service="finance",
    )
