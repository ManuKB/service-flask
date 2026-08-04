import json
import uuid
from typing import Any

from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.push_subscription import PushSubscription
from app.modules.notifications.enums import PushPlatform

_firebase_app: Any | None = None
_firebase_init_attempted = False


def _get_firebase_app() -> Any | None:
    """Lazily imports and initializes the Firebase Admin SDK from the
    configured service account file. Returns None (and never raises) when
    fcm_credentials_path isn't set - or when the optional firebase-admin
    package isn't installed - so Android push is simply a no-op until it's
    configured, without making that heavy dependency required for everyone
    else."""
    global _firebase_app, _firebase_init_attempted
    if _firebase_init_attempted:
        return _firebase_app
    _firebase_init_attempted = True
    path = get_settings().fcm_credentials_path
    if not path:
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials

        _firebase_app = firebase_admin.initialize_app(credentials.Certificate(path))
    except Exception as exc:  # noqa: BLE001 - push delivery must never crash the caller
        print(f"[push] failed to initialize Firebase Admin SDK: {exc}")
        _firebase_app = None
    return _firebase_app


def register_subscription(
    db: Session,
    user_id: uuid.UUID,
    endpoint: str,
    p256dh_key: str | None,
    auth_key: str | None,
    platform: PushPlatform,
) -> PushSubscription:
    """Upsert on endpoint: the same browser subscribing again (e.g. after
    clearing storage and logging back in as someone else on a shared device)
    should just take over the existing row rather than violate the unique
    constraint."""
    subscription = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    if subscription:
        subscription.user_id = user_id
        subscription.p256dh_key = p256dh_key
        subscription.auth_key = auth_key
        subscription.platform = platform
    else:
        subscription = PushSubscription(
            user_id=user_id,
            endpoint=endpoint,
            p256dh_key=p256dh_key,
            auth_key=auth_key,
            platform=platform,
        )
        db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def unregister_subscription(db: Session, user_id: uuid.UUID, endpoint: str) -> None:
    db.execute(
        delete(PushSubscription).where(PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint)
    )
    db.commit()


def _send_one(subscription: PushSubscription, payload: dict) -> int | None:
    """Returns an HTTP status code on failure so the caller can decide
    whether the subscription is stale, or None on success."""
    settings = get_settings()
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh_key, "auth": subscription.auth_key},
            },
            data=json.dumps(payload),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
        )
        return None
    except WebPushException as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        print(f"[push] delivery failed for endpoint {subscription.endpoint}: {exc}")
        return status_code


def _send_fcm_one(token: str, title: str, body: str) -> bool:
    """Returns True if the token is gone and should be pruned (mirrors the
    404/410 handling for web push)."""
    from firebase_admin import messaging

    try:
        messaging.send(
            messaging.Message(notification=messaging.Notification(title=title, body=body), token=token)
        )
        return False
    except messaging.UnregisteredError:
        return True
    except Exception as exc:  # noqa: BLE001 - push delivery must never raise into the caller
        print(f"[push] FCM delivery failed for token {token}: {exc}")
        return False


def send_web_push_to_user(db: Session, user_id: uuid.UUID, title: str, body: str) -> None:
    """Best-effort fan-out to every push subscription (web + Android)
    registered for this user. Failures never raise - a missing/expired push
    subscription must never block the in-app notification or
    reminder-queuing transaction it's called alongside. Subscriptions the
    push service reports as gone are pruned."""
    result = db.scalars(select(PushSubscription).where(PushSubscription.user_id == user_id))
    subscriptions = list(result)
    if not subscriptions:
        return

    stale_ids: list[uuid.UUID] = []

    if get_settings().vapid_private_key:
        payload = {"title": title, "body": body}
        for subscription in (s for s in subscriptions if s.platform == PushPlatform.WEB):
            status_code = _send_one(subscription, payload)
            if status_code in (404, 410):
                stale_ids.append(subscription.id)

    if _get_firebase_app() is not None:
        for subscription in (s for s in subscriptions if s.platform == PushPlatform.ANDROID):
            is_stale = _send_fcm_one(subscription.endpoint, title, body)
            if is_stale:
                stale_ids.append(subscription.id)

    if stale_ids:
        db.execute(delete(PushSubscription).where(PushSubscription.id.in_(stale_ids)))
        db.commit()
