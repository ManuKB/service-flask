import uuid
from datetime import date

from pydantic import BaseModel, Field


class CreateBudgetRequest(BaseModel):
    category_id: uuid.UUID
    month: str = Field(pattern=r"^\d{4}-\d{2}$", description="YYYY-MM")
    limit_amount: float = Field(gt=0)


class UpdateBudgetRequest(BaseModel):
    limit_amount: float = Field(gt=0)


class BudgetStatusResponse(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    category_id: uuid.UUID
    category_name: str
    month: date
    limit_amount: float
    actual_spend: float
    is_over_limit: bool
