import sys
import uuid
from abc import ABC, abstractmethod
from datetime import datetime


class NotificationSender(ABC):
    """Pluggable delivery hook (S3-03: 'shared notification hook'), the same
    shape as invitations.email.EmailSender and finance.reminders.ReminderSender -
    swap the console stub for a real push/SMS/email adapter without touching
    callers."""

    @abstractmethod
    def send_event_reminder(self, family_id: uuid.UUID, event_title: str, event_start_at: datetime) -> None: ...


class ConsoleNotificationSender(NotificationSender):
    """MVP stub - logs the reminder instead of sending a real notification."""

    def send_event_reminder(self, family_id: uuid.UUID, event_title: str, event_start_at: datetime) -> None:
        message = f"[calendar] reminder: event '{event_title}' at {event_start_at} for family {family_id}"
        try:
            print(message)
        except UnicodeEncodeError:
            # Windows consoles often use a legacy codepage (e.g. cp1252)
            # that can't encode emoji/non-BMP characters in a title - fall
            # back to an escaped-but-printable form rather than raising.
            print(message.encode(sys.stdout.encoding or "ascii", errors="backslashreplace").decode())


def get_notification_sender() -> NotificationSender:
    return ConsoleNotificationSender()
