import enum


class PushPlatform(str, enum.Enum):
    WEB = "web"
    # Reserved for a future Flutter app (FCM/APNs) - not wired up yet.
    ANDROID = "android"
    IOS = "ios"
