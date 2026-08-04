from flask import Blueprint, request

from app.core import status
from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.responses import envelope, no_content
from app.modules.notifications.push import service
from app.schemas.push import (
    PushSubscriptionResponse,
    SubscribeRequest,
    UnsubscribeRequest,
    VapidPublicKeyResponse,
)

bp = Blueprint("push", __name__, url_prefix="/push")


@bp.get("/vapid-public-key")
def vapid_public_key():
    return envelope(VapidPublicKeyResponse(public_key=get_settings().vapid_public_key))


@bp.post("/subscriptions")
def subscribe():
    user_id = get_current_user_id()
    db = get_db()
    payload = SubscribeRequest(**request.get_json(force=True))
    subscription = service.register_subscription(
        db,
        user_id,
        payload.endpoint,
        payload.keys.p256dh if payload.keys else None,
        payload.keys.auth if payload.keys else None,
        payload.platform,
    )
    return envelope(PushSubscriptionResponse.model_validate(subscription), status.HTTP_201_CREATED)


@bp.post("/unsubscribe")
def unsubscribe():
    user_id = get_current_user_id()
    db = get_db()
    payload = UnsubscribeRequest(**request.get_json(force=True))
    service.unregister_subscription(db, user_id, payload.endpoint)
    return no_content()
