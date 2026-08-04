import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.modules.finance.enums import CategoryType


class CategoryError(Exception):
    """Raised for any category-domain failure the router should turn into an HTTP error."""


def create_category(db: Session, family_id: uuid.UUID, name: str, type_: CategoryType) -> Category:
    existing = db.scalar(select(Category).where(Category.family_id == family_id, Category.name == name))
    if existing:
        raise CategoryError("A category with this name already exists in this family")
    category = Category(family_id=family_id, name=name, type=type_)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def list_categories(db: Session, family_id: uuid.UUID) -> list[Category]:
    result = db.scalars(select(Category).where(Category.family_id == family_id).order_by(Category.name))
    return list(result)
