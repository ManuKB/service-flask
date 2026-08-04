import uuid

from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AppError
from app.core.responses import envelope, envelope_list, no_content
from app.modules.permissions.rbac import require_active_member
from app.modules.shopping import service
from app.schemas.shopping import (
    CreateShoppingItemRequest,
    CreateShoppingListRequest,
    PurchaseItemRequest,
    RenameShoppingListRequest,
    ShoppingItemResponse,
    ShoppingListResponse,
    UpdateShoppingItemRequest,
)

bp = Blueprint("shopping", __name__, url_prefix="/families/<uuid:family_id>/shopping/lists")


@bp.post("")
def create_list(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = CreateShoppingListRequest(**request.get_json(force=True))
    shopping_list = service.create_list(db, family_id, user_id, payload.name)
    return envelope(ShoppingListResponse.model_validate(shopping_list), status.HTTP_201_CREATED)


@bp.get("")
def list_lists(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    lists = service.list_lists(db, family_id)
    return envelope_list([ShoppingListResponse.model_validate(lst) for lst in lists])


@bp.patch("/<uuid:list_id>")
def rename_list(family_id: uuid.UUID, list_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = RenameShoppingListRequest(**request.get_json(force=True))
    try:
        shopping_list = service.rename_list(db, family_id, list_id, payload.name)
    except service.ShoppingError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(ShoppingListResponse.model_validate(shopping_list))


@bp.delete("/<uuid:list_id>")
def delete_list(family_id: uuid.UUID, list_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    try:
        service.delete_list(db, family_id, list_id)
    except service.ShoppingError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return no_content()


@bp.post("/<uuid:list_id>/items")
def add_item(family_id: uuid.UUID, list_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = CreateShoppingItemRequest(**request.get_json(force=True))
    try:
        item = service.add_item(
            db, family_id, user_id, list_id, payload.name, payload.quantity, payload.notes, payload.store
        )
    except service.ShoppingError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(ShoppingItemResponse.model_validate(item), status.HTTP_201_CREATED)


@bp.get("/<uuid:list_id>/items")
def list_items(family_id: uuid.UUID, list_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    store = request.args.get("store")
    try:
        items = service.list_items(db, family_id, list_id, store)
    except service.ShoppingError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope_list([ShoppingItemResponse.model_validate(i) for i in items])


@bp.patch("/<uuid:list_id>/items/<uuid:item_id>")
def update_item(family_id: uuid.UUID, list_id: uuid.UUID, item_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = UpdateShoppingItemRequest(**request.get_json(force=True))
    try:
        item = service.update_item(
            db,
            family_id,
            list_id,
            item_id,
            name=payload.name,
            quantity=payload.quantity,
            clear_quantity=payload.clear_quantity,
            notes=payload.notes,
            clear_notes=payload.clear_notes,
            store=payload.store,
            clear_store=payload.clear_store,
        )
    except service.ShoppingError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(ShoppingItemResponse.model_validate(item))


@bp.delete("/<uuid:list_id>/items/<uuid:item_id>")
def delete_item(family_id: uuid.UUID, list_id: uuid.UUID, item_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    try:
        service.delete_item(db, family_id, list_id, item_id)
    except service.ShoppingError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return no_content()


@bp.post("/<uuid:list_id>/items/<uuid:item_id>/purchase")
def mark_purchased(family_id: uuid.UUID, list_id: uuid.UUID, item_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    body = request.get_json(silent=True, force=True) or {}
    payload = PurchaseItemRequest(**body)
    try:
        item = service.mark_purchased(
            db,
            family_id,
            user_id,
            list_id,
            item_id,
            amount=payload.amount,
            account_id=payload.account_id,
            category_id=payload.category_id,
            occurred_on=payload.occurred_on,
        )
    except service.ShoppingValidationError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except service.ShoppingError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(ShoppingItemResponse.model_validate(item))


@bp.post("/<uuid:list_id>/items/<uuid:item_id>/restore")
def restore_item(family_id: uuid.UUID, list_id: uuid.UUID, item_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    try:
        item = service.restore_item(db, family_id, user_id, list_id, item_id)
    except service.ShoppingError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(ShoppingItemResponse.model_validate(item))
