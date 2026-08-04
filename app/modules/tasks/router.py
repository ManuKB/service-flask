import uuid
from datetime import date

from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AppError
from app.core.responses import envelope, envelope_list, no_content
from app.models.task import Task
from app.modules.audit.service import list_events_for_entity
from app.modules.permissions.rbac import require_active_member
from app.modules.tasks import service
from app.schemas.audit_event import AuditEventResponse
from app.schemas.tasks import (
    AddChecklistItemRequest,
    ChecklistItemResponse,
    CreateCommentRequest,
    CreateTaskRequest,
    SetTaskStatusRequest,
    TaskCommentResponse,
    TaskResponse,
    UpdateChecklistItemRequest,
    UpdateTaskRequest,
)

bp = Blueprint("tasks", __name__, url_prefix="/families/<uuid:family_id>/tasks")


def _to_task_response(db, task: Task) -> TaskResponse:
    checklist_items = service.list_checklist_items(db, task.id)
    return TaskResponse(
        id=task.id,
        family_id=task.family_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        assignee_user_id=task.assignee_user_id,
        due_date=task.due_date,
        recurrence=task.recurrence,
        parent_task_id=task.parent_task_id,
        is_overdue=service.is_overdue(task, date.today()),
        completed_at=task.completed_at,
        checklist_items=[ChecklistItemResponse.model_validate(item) for item in checklist_items],
        created_by_user_id=task.created_by_user_id,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@bp.post("")
def create_task(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = CreateTaskRequest(**request.get_json(force=True))
    try:
        task = service.create_task(
            db,
            family_id,
            user_id,
            payload.title,
            payload.description,
            payload.priority,
            payload.assignee_user_id,
            payload.due_date,
            payload.recurrence,
            payload.checklist_items,
        )
    except service.TaskError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return envelope(_to_task_response(db, task), status.HTTP_201_CREATED)


@bp.get("")
def list_tasks(family_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    tasks = service.list_tasks(db, family_id)
    return envelope_list([_to_task_response(db, task) for task in tasks])


@bp.get("/<uuid:task_id>")
def get_task(family_id: uuid.UUID, task_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    try:
        task = service.get_task(db, family_id, task_id)
    except service.TaskError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(_to_task_response(db, task))


@bp.patch("/<uuid:task_id>")
def update_task(family_id: uuid.UUID, task_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = UpdateTaskRequest(**request.get_json(force=True))
    try:
        task = service.update_task(
            db,
            family_id,
            user_id,
            task_id,
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
            assignee_user_id=payload.assignee_user_id,
            clear_assignee=payload.clear_assignee,
            due_date=payload.due_date,
            clear_due_date=payload.clear_due_date,
            recurrence=payload.recurrence,
            clear_recurrence=payload.clear_recurrence,
        )
    except service.TaskError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return envelope(_to_task_response(db, task))


@bp.patch("/<uuid:task_id>/status")
def set_task_status(family_id: uuid.UUID, task_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = SetTaskStatusRequest(**request.get_json(force=True))
    try:
        task = service.set_task_status(db, family_id, user_id, task_id, payload.status)
    except service.TaskError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return envelope(_to_task_response(db, task))


@bp.delete("/<uuid:task_id>")
def delete_task(family_id: uuid.UUID, task_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    try:
        service.delete_task(db, family_id, task_id)
    except service.TaskError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return no_content()


@bp.post("/<uuid:task_id>/checklist")
def add_checklist_item(family_id: uuid.UUID, task_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = AddChecklistItemRequest(**request.get_json(force=True))
    try:
        item = service.add_checklist_item(db, family_id, task_id, payload.label)
    except service.TaskError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(ChecklistItemResponse.model_validate(item), status.HTTP_201_CREATED)


@bp.patch("/<uuid:task_id>/checklist/<uuid:item_id>")
def update_checklist_item(family_id: uuid.UUID, task_id: uuid.UUID, item_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = UpdateChecklistItemRequest(**request.get_json(force=True))
    try:
        item = service.update_checklist_item(
            db, family_id, task_id, item_id, label=payload.label, is_completed=payload.is_completed
        )
    except service.TaskError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(ChecklistItemResponse.model_validate(item))


@bp.delete("/<uuid:task_id>/checklist/<uuid:item_id>")
def delete_checklist_item(family_id: uuid.UUID, task_id: uuid.UUID, item_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    try:
        service.delete_checklist_item(db, family_id, task_id, item_id)
    except service.TaskError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return no_content()


@bp.post("/<uuid:task_id>/comments")
def add_comment(family_id: uuid.UUID, task_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = CreateCommentRequest(**request.get_json(force=True))
    try:
        comment = service.add_comment(db, family_id, user_id, task_id, payload.body)
    except service.TaskError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope(TaskCommentResponse.model_validate(comment), status.HTTP_201_CREATED)


@bp.get("/<uuid:task_id>/comments")
def list_comments(family_id: uuid.UUID, task_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    try:
        comments = service.list_comments(db, family_id, task_id)
    except service.TaskError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return envelope_list([TaskCommentResponse.model_validate(c) for c in comments])


@bp.get("/<uuid:task_id>/activity")
def get_task_activity(family_id: uuid.UUID, task_id: uuid.UUID):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    try:
        service.get_task(db, family_id, task_id)
    except service.TaskError as exc:
        raise AppError(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    events = list_events_for_entity(db, "Task", task_id)
    return envelope_list([AuditEventResponse.model_validate(e) for e in events])
