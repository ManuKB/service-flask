import calendar as calendar_module
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.family_membership import FamilyMembership
from app.models.task import Task
from app.models.task_checklist_item import TaskChecklistItem
from app.models.task_comment import TaskComment
from app.modules.audit.service import record_event
from app.modules.notifications import service as notifications_service
from app.modules.notifications.push import service as push_service
from app.modules.permissions.roles import MembershipStatus
from app.modules.tasks.enums import TaskPriority, TaskRecurrence, TaskStatus


class TaskError(Exception):
    """Raised for any task-domain failure the router should turn into an HTTP error."""


def _validate_assignee(db: Session, family_id: uuid.UUID, assignee_user_id: uuid.UUID) -> None:
    membership = db.scalar(
        select(FamilyMembership).where(
            FamilyMembership.family_id == family_id, FamilyMembership.user_id == assignee_user_id
        )
    )
    if not membership:
        raise TaskError("Assignee is not a member of this family")


def _advance_due_date(current: date, recurrence: TaskRecurrence) -> date:
    """Steps a task's due date forward one cycle - month advances clamp the
    day to the target month's length (e.g. Jan 31 monthly -> Feb 28/29)."""
    if recurrence == TaskRecurrence.DAILY:
        return current + timedelta(days=1)
    if recurrence == TaskRecurrence.WEEKLY:
        return current + timedelta(days=7)
    if recurrence == TaskRecurrence.MONTHLY:
        month_index = current.month  # current.month - 1 + 1
        year = current.year + month_index // 12
        month = month_index % 12 + 1
        day = min(current.day, calendar_module.monthrange(year, month)[1])
        return current.replace(year=year, month=month, day=day)
    raise ValueError(f"Unsupported recurrence: {recurrence}")


def is_overdue(task: Task, today: date) -> bool:
    return task.due_date is not None and task.due_date < today and task.status != TaskStatus.DONE


def create_task(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
    description: str | None,
    priority: TaskPriority,
    assignee_user_id: uuid.UUID | None,
    due_date: date | None,
    recurrence: TaskRecurrence | None,
    checklist_labels: list[str],
) -> Task:
    if assignee_user_id is not None:
        _validate_assignee(db, family_id, assignee_user_id)
    if recurrence is not None and due_date is None:
        raise TaskError("A recurring task needs a due date")

    task = Task(
        family_id=family_id,
        title=title,
        description=description,
        priority=priority,
        assignee_user_id=assignee_user_id,
        due_date=due_date,
        recurrence=recurrence,
        created_by_user_id=user_id,
    )
    db.add(task)
    db.flush()

    for position, label in enumerate(checklist_labels):
        db.add(TaskChecklistItem(task_id=task.id, label=label, position=position))

    db.commit()
    db.refresh(task)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=user_id,
        action="task.created",
        entity_type="Task",
        entity_id=task.id,
        new_value={"title": title, "assignee_user_id": str(assignee_user_id) if assignee_user_id else None},
        source_service="tasks",
    )

    if assignee_user_id is not None:
        _notify_assignment(db, family_id, assignee_user_id, task)

    return task


def _notify_assignment(db: Session, family_id: uuid.UUID, assignee_user_id: uuid.UUID, task: Task) -> None:
    title = "New task assigned"
    body = f"You were assigned: {task.title}"
    notification = notifications_service.notify_user(
        db, family_id, assignee_user_id, title, body, task_id=task.id
    )
    db.commit()
    push_service.send_web_push_to_user(db, notification.user_id, title, body)


def get_task(db: Session, family_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    task = db.get(Task, task_id)
    if not task or task.family_id != family_id:
        raise TaskError("Task not found")
    return task


def list_tasks(db: Session, family_id: uuid.UUID) -> list[Task]:
    result = db.scalars(
        select(Task).where(Task.family_id == family_id).order_by(Task.due_date.is_(None), Task.due_date, Task.created_at)
    )
    return list(result)


def list_checklist_items(db: Session, task_id: uuid.UUID) -> list[TaskChecklistItem]:
    result = db.scalars(
        select(TaskChecklistItem).where(TaskChecklistItem.task_id == task_id).order_by(TaskChecklistItem.position)
    )
    return list(result)


def update_task(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    task_id: uuid.UUID,
    *,
    title: str | None = None,
    description: str | None = None,
    priority: TaskPriority | None = None,
    assignee_user_id: uuid.UUID | None = None,
    clear_assignee: bool = False,
    due_date: date | None = None,
    clear_due_date: bool = False,
    recurrence: TaskRecurrence | None = None,
    clear_recurrence: bool = False,
) -> Task:
    task = get_task(db, family_id, task_id)

    previous_assignee = task.assignee_user_id
    new_assignee = task.assignee_user_id

    if title is not None:
        task.title = title
    if description is not None:
        task.description = description
    if priority is not None:
        task.priority = priority

    if clear_assignee:
        new_assignee = None
    elif assignee_user_id is not None:
        _validate_assignee(db, family_id, assignee_user_id)
        new_assignee = assignee_user_id
    task.assignee_user_id = new_assignee

    if clear_due_date:
        task.due_date = None
    elif due_date is not None:
        task.due_date = due_date

    if clear_recurrence:
        task.recurrence = None
    elif recurrence is not None:
        task.recurrence = recurrence

    if task.recurrence is not None and task.due_date is None:
        raise TaskError("A recurring task needs a due date")

    db.commit()
    db.refresh(task)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=user_id,
        action="task.updated",
        entity_type="Task",
        entity_id=task.id,
        source_service="tasks",
    )

    if new_assignee is not None and new_assignee != previous_assignee:
        record_event(
            db,
            family_id=family_id,
            actor_user_id=user_id,
            action="task.assigned",
            entity_type="Task",
            entity_id=task.id,
            old_value={"assignee_user_id": str(previous_assignee) if previous_assignee else None},
            new_value={"assignee_user_id": str(new_assignee)},
            source_service="tasks",
        )
        _notify_assignment(db, family_id, new_assignee, task)

    return task


_STATUS_LABELS = {
    TaskStatus.TODO: "To Do",
    TaskStatus.IN_PROGRESS: "In Progress",
    TaskStatus.DONE: "Done",
}


def set_task_status(
    db: Session, family_id: uuid.UUID, user_id: uuid.UUID, task_id: uuid.UUID, new_status: TaskStatus
) -> Task:
    task = get_task(db, family_id, task_id)
    old_status = task.status
    task.status = new_status

    if new_status == TaskStatus.DONE and old_status != TaskStatus.DONE:
        task.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        if task.recurrence is not None and task.due_date is not None:
            _spawn_next_occurrence(db, task)
        notifications_service.delete_notifications_for_task(db, task_id)
    elif new_status != TaskStatus.DONE:
        task.completed_at = None

    db.commit()
    db.refresh(task)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=user_id,
        action="task.status_changed",
        entity_type="Task",
        entity_id=task.id,
        old_value={"status": old_status.value},
        new_value={"status": new_status.value},
        source_service="tasks",
    )

    if old_status != new_status:
        _notify_status_change(db, task, actor_user_id=user_id, new_status=new_status)

    return task


def _notify_status_change(
    db: Session, task: Task, actor_user_id: uuid.UUID, new_status: TaskStatus
) -> None:
    """Tells the task's owner (whoever created it) when its status changes -
    skipped when the owner is the one who made the change, since notifying
    someone about their own action is just noise."""
    if task.created_by_user_id == actor_user_id:
        return
    title = "Task status updated"
    body = f'"{task.title}" is now {_STATUS_LABELS[new_status]}'
    notification = notifications_service.notify_user(
        db, task.family_id, task.created_by_user_id, title, body, task_id=task.id
    )
    db.commit()
    push_service.send_web_push_to_user(db, notification.user_id, title, body)


def _spawn_next_occurrence(db: Session, completed_task: Task) -> Task:
    """S4-03: 'Completed recurring task creates the next occurrence' - a
    fresh Task row (own id, own checklist reset to incomplete), linked back
    via parent_task_id so the series has a traceable history."""
    assert completed_task.due_date is not None and completed_task.recurrence is not None
    next_due_date = _advance_due_date(completed_task.due_date, completed_task.recurrence)

    next_task = Task(
        family_id=completed_task.family_id,
        title=completed_task.title,
        description=completed_task.description,
        priority=completed_task.priority,
        assignee_user_id=completed_task.assignee_user_id,
        due_date=next_due_date,
        recurrence=completed_task.recurrence,
        parent_task_id=completed_task.id,
        created_by_user_id=completed_task.created_by_user_id,
    )
    db.add(next_task)
    db.flush()

    previous_items = list_checklist_items(db, completed_task.id)
    for item in previous_items:
        db.add(TaskChecklistItem(task_id=next_task.id, label=item.label, position=item.position))

    return next_task


def delete_task(db: Session, family_id: uuid.UUID, task_id: uuid.UUID) -> None:
    task = get_task(db, family_id, task_id)

    checklist_items = db.scalars(select(TaskChecklistItem).where(TaskChecklistItem.task_id == task_id))
    for item in checklist_items:
        db.delete(item)
    comments = db.scalars(select(TaskComment).where(TaskComment.task_id == task_id))
    for comment in comments:
        db.delete(comment)
    notifications_service.delete_notifications_for_task(db, task_id)

    # Flush the dependents' deletes first - without an ORM relationship()
    # linking Task to these tables, the unit of work has no dependency info
    # to order a single flush correctly (same class of bug fixed earlier for
    # calendar.events.service.delete_event).
    db.flush()
    db.delete(task)
    db.commit()


def add_checklist_item(
    db: Session, family_id: uuid.UUID, task_id: uuid.UUID, label: str
) -> TaskChecklistItem:
    get_task(db, family_id, task_id)
    existing = list_checklist_items(db, task_id)
    item = TaskChecklistItem(task_id=task_id, label=label, position=len(existing))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_checklist_item(
    db: Session,
    family_id: uuid.UUID,
    task_id: uuid.UUID,
    item_id: uuid.UUID,
    *,
    label: str | None = None,
    is_completed: bool | None = None,
) -> TaskChecklistItem:
    get_task(db, family_id, task_id)
    item = db.get(TaskChecklistItem, item_id)
    if not item or item.task_id != task_id:
        raise TaskError("Checklist item not found")
    if label is not None:
        item.label = label
    if is_completed is not None:
        # S4-03: completing every checklist item must never itself flip the
        # task's status - only set_task_status() (an explicit user action) does.
        item.is_completed = is_completed
    db.commit()
    db.refresh(item)
    return item


def delete_checklist_item(db: Session, family_id: uuid.UUID, task_id: uuid.UUID, item_id: uuid.UUID) -> None:
    get_task(db, family_id, task_id)
    item = db.get(TaskChecklistItem, item_id)
    if not item or item.task_id != task_id:
        raise TaskError("Checklist item not found")
    db.delete(item)
    db.commit()


def add_comment(db: Session, family_id: uuid.UUID, user_id: uuid.UUID, task_id: uuid.UUID, body: str) -> TaskComment:
    get_task(db, family_id, task_id)
    comment = TaskComment(task_id=task_id, author_user_id=user_id, body=body)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def list_comments(db: Session, family_id: uuid.UUID, task_id: uuid.UUID) -> list[TaskComment]:
    get_task(db, family_id, task_id)
    result = db.scalars(
        select(TaskComment).where(TaskComment.task_id == task_id).order_by(TaskComment.created_at)
    )
    return list(result)


def process_due_task_reminders(db: Session, family_id: uuid.UUID, now: datetime | None = None) -> list[Task]:
    """Due-soon (24h before due_date) and overdue (due_date has passed)
    notifications for tasks - same shared scheduler pass, same idempotency
    approach as calendar reminders and bill reminders, just keyed off
    due_soon_notified_at/overdue_notified_at directly on Task instead of a
    separate Reminder row (there's nothing user-configurable here - both
    checks are automatic once a task has a due date)."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is not None:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)
    today = now.date()

    result = db.scalars(
        select(Task).where(
            Task.family_id == family_id,
            Task.status != TaskStatus.DONE,
            Task.due_date.is_not(None),
        )
    )
    # Two passes, matching calendar/bill reminders' ordering: first decide
    # what's due and durably flip the idempotency flags in one commit, THEN
    # send the actual notifications - so a crash/failure in delivery can
    # never cause a flag to go uncommitted and re-fire the same alert forever.
    due_soon: list[Task] = []
    overdue: list[Task] = []
    for task in result:
        due_soon_at = datetime.combine(task.due_date - timedelta(days=1), datetime.min.time())
        if task.due_soon_notified_at is None and now >= due_soon_at and today <= task.due_date:
            task.due_soon_notified_at = now
            due_soon.append(task)
        if task.overdue_notified_at is None and today > task.due_date:
            task.overdue_notified_at = now
            overdue.append(task)

    notified = due_soon + overdue
    if not notified:
        return []

    db.commit()
    for task in notified:
        db.refresh(task)

    for task in due_soon:
        _notify_task_event(db, task, "Task due soon", f"{task.title} is due {task.due_date.strftime('%b %d, %Y')}")
    for task in overdue:
        _notify_task_event(
            db, task, "Task overdue", f"{task.title} was due {task.due_date.strftime('%b %d, %Y')}"
        )
    return notified


def _notify_task_event(db: Session, task: Task, title: str, body: str) -> None:
    if task.assignee_user_id is not None:
        notification = notifications_service.notify_user(
            db, task.family_id, task.assignee_user_id, title, body, task_id=task.id
        )
        db.commit()
        push_service.send_web_push_to_user(db, notification.user_id, title, body)
    else:
        notifications = notifications_service.notify_family(db, task.family_id, title, body, task_id=task.id)
        db.commit()
        for notification in notifications:
            push_service.send_web_push_to_user(db, notification.user_id, title, body)
