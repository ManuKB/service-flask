import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.modules.notifications.enums import PushPlatform


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    platform: Mapped[PushPlatform] = mapped_column(Enum(PushPlatform), default=PushPlatform.WEB, nullable=False)
    # Web push: the browser push service URL, unique per browser/device registration.
    # Doubles as the natural dedup key for future platforms (FCM/APNs device token).
    # Web push: the browser push service URL. Android/iOS: the bare FCM/APNs
    # device token.
    endpoint: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    # Web push only - the subscription's encryption keys (null for android/ios).
    p256dh_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
