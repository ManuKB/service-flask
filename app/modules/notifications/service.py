import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models.family_membership import FamilyMembership
from app.models.notification import Notification
from app.modules.permissions.roles import MembershipStatus


class NotificationError(Exception):
    """Raised for any notification-domain failure the router should turn into an HTTP error."""


def _active_member_user_ids(db: Session, family_id: uuid.UUID) -> list[uuid.UUID]:
    result = db.scalars(
        select(FamilyMembership.user_id).where(
            FamilyMembership.family_id == family_id,
            FamilyMembership.status == MembershipStatus.ACTIVE,
        )
    )
    return list(result)


def notify_family(
    db: Session,
    family_id: uuid.UUID,
    title: str,
    body: str,
    event_id: uuid.UUID | None = None,
    bill_id: uuid.UUID | None = None,
    task_id: uuid.UUID | None = None,
) -> list[Notification]:
    """Creates one in-app Notification per active family member. Caller is
    responsible for committing (kept out of this function so callers that
    also mutate other rows in the same transaction - e.g. reminders setting
    queued_at - do it in one commit). At most one of event_id/bill_id/task_id
    should be set, so a click on the notification resolves to exactly one
    thing."""
    user_ids = _active_member_user_ids(db, family_id)
    notifications = [
        Notification(
            family_id=family_id,
            user_id=user_id,
            title=title,
            body=body,
            event_id=event_id,
            bill_id=bill_id,
            task_id=task_id,
        )
        for user_id in user_ids
    ]
    db.add_all(notifications)
    return notifications


def notify_user(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
    body: str,
    event_id: uuid.UUID | None = None,
    bill_id: uuid.UUID | None = None,
    task_id: uuid.UUID | None = None,
) -> Notification:
    """Single-recipient counterpart of notify_family - for things that
    concern one specific person rather than the whole family (task
    assignment creates one notification for the assignee, not everyone)."""
    notification = Notification(
        family_id=family_id, user_id=user_id, title=title, body=body, event_id=event_id, bill_id=bill_id, task_id=task_id
    )
    db.add(notification)
    return notification


def list_notifications(db: Session, family_id: uuid.UUID, user_id: uuid.UUID) -> list[Notification]:
    result = db.scalars(
        select(Notification)
        .where(Notification.family_id == family_id, Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    return list(result)


def get_unread_count(db: Session, family_id: uuid.UUID, user_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.family_id == family_id,
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
    )


def mark_read(db: Session, family_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID) -> Notification:
    notification = db.get(Notification, notification_id)
    if not notification or notification.family_id != family_id or notification.user_id != user_id:
        raise NotificationError("Notification not found")
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification


def mark_all_read(db: Session, family_id: uuid.UUID, user_id: uuid.UUID) -> None:
    db.execute(
        update(Notification)
        .where(
            Notification.family_id == family_id,
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )
    db.commit()


def delete_notification(db: Session, family_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID) -> None:
    """Dismisses a single notification from the caller's own feed."""
    notification = db.get(Notification, notification_id)
    if not notification or notification.family_id != family_id or notification.user_id != user_id:
        raise NotificationError("Notification not found")
    db.delete(notification)
    db.commit()


def clear_all_notifications(db: Session, family_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Dismisses every notification in the caller's own feed - the "Clear all" counterpart of mark_all_read."""
    db.execute(delete(Notification).where(Notification.family_id == family_id, Notification.user_id == user_id))
    db.commit()


def delete_notifications_for_event(db: Session, event_id: uuid.UUID) -> None:
    """Once an event (or one of its occurrences) is marked complete, its
    'this is due' reminder notification is moot - clear it out of everyone's
    feed rather than leaving it to sit there read or unread. Caller commits
    (same convention as notify_family) so this can share a transaction with
    the completion itself."""
    db.execute(delete(Notification).where(Notification.event_id == event_id))


def delete_notifications_for_bill(db: Session, bill_id: uuid.UUID) -> None:
    """Bill counterpart of delete_notifications_for_event - called when a
    bill's current cycle is marked complete."""
    db.execute(delete(Notification).where(Notification.bill_id == bill_id))


def delete_notifications_for_task(db: Session, task_id: uuid.UUID) -> None:
    """Task counterpart of delete_notifications_for_event - called when a
    task is marked done (its due-soon/overdue/assignment notifications are
    all moot once it's complete)."""
    db.execute(delete(Notification).where(Notification.task_id == task_id))
