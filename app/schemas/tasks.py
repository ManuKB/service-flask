import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tasks.enums import TaskPriority, TaskRecurrence, TaskStatus


class CreateTaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_user_id: uuid.UUID | None = None
    due_date: date | None = None
    recurrence: TaskRecurrence | None = None
    checklist_items: list[str] = Field(default_factory=list)


class UpdateTaskRequest(BaseModel):
    """A None field means "leave unchanged"; to actually clear an optional
    field, use the matching clear_* flag (same convention as calendar
    events' clear_recurrence)."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    priority: TaskPriority | None = None
    assignee_user_id: uuid.UUID | None = None
    clear_assignee: bool = False
    due_date: date | None = None
    clear_due_date: bool = False
    recurrence: TaskRecurrence | None = None
    clear_recurrence: bool = False


class SetTaskStatusRequest(BaseModel):
    status: TaskStatus


class ChecklistItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    is_completed: bool
    position: int


class AddChecklistItemRequest(BaseModel):
    label: str = Field(min_length=1, max_length=255)


class UpdateChecklistItemRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=255)
    is_completed: bool | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    assignee_user_id: uuid.UUID | None
    due_date: date | None
    recurrence: TaskRecurrence | None
    parent_task_id: uuid.UUID | None
    is_overdue: bool
    completed_at: datetime | None
    checklist_items: list[ChecklistItemResponse]
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class CreateCommentRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class TaskCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    author_user_id: uuid.UUID
    body: str
    created_at: datetime
