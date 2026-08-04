import uuid

from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AppError
from app.core.responses import envelope, envelope_list
from app.modules.finance.categories import service
from app.modules.permissions.rbac import require_active_member
from app.schemas.finance.categories import CategoryResponse, CreateCategoryRequest

bp = Blueprint("finance_categories", __name__, url_prefix="/families/<uuid:family_id>/finance/categories")


@bp.post("")
def create_category(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = CreateCategoryRequest(**request.get_json(force=True))
    try:
        category = service.create_category(db, family_id, payload.name, payload.type)
    except service.CategoryError as exc:
        raise AppError(status.HTTP_409_CONFLICT, str(exc)) from exc
    return envelope(CategoryResponse.model_validate(category), status.HTTP_201_CREATED)


@bp.get("")
def list_categories(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    categories = service.list_categories(db, family_id)
    return envelope_list([CategoryResponse.model_validate(c) for c in categories])
