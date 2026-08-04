import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.shopping_item import ShoppingItem
from app.models.shopping_list import ShoppingList
from app.modules.finance.enums import CategoryType
from app.modules.finance.transactions import service as transactions_service


class ShoppingError(Exception):
    """Raised for any shopping-domain "not found" failure the router should turn into a 404."""


class ShoppingValidationError(ShoppingError):
    """Raised for a shopping-domain input failure the router should turn into a 400."""


def create_list(db: Session, family_id: uuid.UUID, user_id: uuid.UUID, name: str) -> ShoppingList:
    shopping_list = ShoppingList(family_id=family_id, name=name, created_by_user_id=user_id)
    db.add(shopping_list)
    db.commit()
    db.refresh(shopping_list)
    return shopping_list


def list_lists(db: Session, family_id: uuid.UUID) -> list[ShoppingList]:
    result = db.scalars(
        select(ShoppingList).where(ShoppingList.family_id == family_id).order_by(ShoppingList.created_at)
    )
    return list(result)


def get_list(db: Session, family_id: uuid.UUID, list_id: uuid.UUID) -> ShoppingList:
    shopping_list = db.get(ShoppingList, list_id)
    if not shopping_list or shopping_list.family_id != family_id:
        raise ShoppingError("Shopping list not found")
    return shopping_list


def rename_list(db: Session, family_id: uuid.UUID, list_id: uuid.UUID, name: str) -> ShoppingList:
    shopping_list = get_list(db, family_id, list_id)
    shopping_list.name = name
    db.commit()
    db.refresh(shopping_list)
    return shopping_list


def delete_list(db: Session, family_id: uuid.UUID, list_id: uuid.UUID) -> None:
    shopping_list = get_list(db, family_id, list_id)
    items = db.scalars(select(ShoppingItem).where(ShoppingItem.list_id == list_id))
    for item in items:
        db.delete(item)
    # Flush the items' deletes first - without an ORM relationship() linking
    # ShoppingList to ShoppingItem, the unit of work has no dependency info
    # to order a single flush correctly (same class of bug fixed for
    # calendar.events.service.delete_event and tasks.service.delete_task).
    db.flush()
    db.delete(shopping_list)
    db.commit()


def add_item(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    list_id: uuid.UUID,
    name: str,
    quantity: str | None,
    notes: str | None,
    store: str | None,
) -> ShoppingItem:
    get_list(db, family_id, list_id)
    item = ShoppingItem(
        list_id=list_id, name=name, quantity=quantity, notes=notes, store=store, created_by_user_id=user_id
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_items(db: Session, family_id: uuid.UUID, list_id: uuid.UUID, store: str | None = None) -> list[ShoppingItem]:
    get_list(db, family_id, list_id)
    query = select(ShoppingItem).where(ShoppingItem.list_id == list_id)
    if store is not None:
        query = query.where(ShoppingItem.store == store)
    result = db.scalars(query.order_by(ShoppingItem.is_purchased, ShoppingItem.created_at))
    return list(result)


def _get_item(db: Session, family_id: uuid.UUID, list_id: uuid.UUID, item_id: uuid.UUID) -> ShoppingItem:
    get_list(db, family_id, list_id)
    item = db.get(ShoppingItem, item_id)
    if not item or item.list_id != list_id:
        raise ShoppingError("Shopping item not found")
    return item


def update_item(
    db: Session,
    family_id: uuid.UUID,
    list_id: uuid.UUID,
    item_id: uuid.UUID,
    *,
    name: str | None = None,
    quantity: str | None = None,
    clear_quantity: bool = False,
    notes: str | None = None,
    clear_notes: bool = False,
    store: str | None = None,
    clear_store: bool = False,
) -> ShoppingItem:
    item = _get_item(db, family_id, list_id, item_id)
    if name is not None:
        item.name = name
    if clear_quantity:
        item.quantity = None
    elif quantity is not None:
        item.quantity = quantity
    if clear_notes:
        item.notes = None
    elif notes is not None:
        item.notes = notes
    if clear_store:
        item.store = None
    elif store is not None:
        item.store = store
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, family_id: uuid.UUID, list_id: uuid.UUID, item_id: uuid.UUID) -> None:
    item = _get_item(db, family_id, list_id, item_id)
    db.delete(item)
    db.commit()


def mark_purchased(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    list_id: uuid.UUID,
    item_id: uuid.UUID,
    *,
    amount: float | None = None,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    occurred_on: date | None = None,
) -> ShoppingItem:
    item = _get_item(db, family_id, list_id, item_id)
    item.is_purchased = True
    item.purchased_by_user_id = user_id
    item.purchased_at = datetime.now(timezone.utc).replace(tzinfo=None)

    if amount is not None:
        if account_id is None or category_id is None:
            raise ShoppingValidationError("Select an account and category to record this purchase as an expense")
        try:
            transaction = transactions_service.create_transaction(
                db,
                family_id,
                user_id,
                account_id,
                category_id,
                CategoryType.EXPENSE,
                amount,
                occurred_on or date.today(),
                f"Shopping: {item.name}",
                None,
            )
        except transactions_service.TransactionError as exc:
            raise ShoppingValidationError(str(exc)) from exc
        item.transaction_id = transaction.id

    db.commit()
    db.refresh(item)
    return item


def restore_item(
    db: Session, family_id: uuid.UUID, user_id: uuid.UUID, list_id: uuid.UUID, item_id: uuid.UUID
) -> ShoppingItem:
    item = _get_item(db, family_id, list_id, item_id)
    item.is_purchased = False
    item.purchased_by_user_id = None
    item.purchased_at = None

    if item.transaction_id is not None:
        # Undo the expense the same way finance.bills does: delete the
        # Transaction that was recorded for this purchase.
        transaction_id = item.transaction_id
        item.transaction_id = None
        db.flush()
        transactions_service.delete_transaction(db, family_id, user_id, transaction_id)

    db.commit()
    db.refresh(item)
    return item
