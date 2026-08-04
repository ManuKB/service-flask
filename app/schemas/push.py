import uuid

from pydantic import BaseModel, ConfigDict

from app.modules.notifications.enums import PushPlatform


class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class SubscribeRequest(BaseModel):
    endpoint: str
    # Web push carries encryption keys; Android/iOS register a bare FCM/APNs
    # device token via `endpoint` and omit this.
    keys: PushSubscriptionKeys | None = None
    platform: PushPlatform = PushPlatform.WEB


class UnsubscribeRequest(BaseModel):
    endpoint: str


class PushSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: PushPlatform
    endpoint: str


class VapidPublicKeyResponse(BaseModel):
    public_key: str
