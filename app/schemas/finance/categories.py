import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.finance.enums import CategoryType


class CreateCategoryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: CategoryType


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    name: str
    type: CategoryType
    created_at: datetime
