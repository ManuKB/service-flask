import uuid
from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal


class ReminderSender(ABC):
    """Pluggable delivery hook (S2-04: 'reminder hook'), same shape as
    invitations.email.EmailSender - swap the console stub for a real
    push/SMS/email adapter without touching callers."""

    @abstractmethod
    def send_bill_reminder(
        self, family_id: uuid.UUID, bill_name: str, amount: Decimal, due_date: date
    ) -> None: ...


class ConsoleReminderSender(ReminderSender):
    """MVP stub - logs the reminder instead of sending a real notification."""

    def send_bill_reminder(
        self, family_id: uuid.UUID, bill_name: str, amount: Decimal, due_date: date
    ) -> None:
        print(f"[finance] reminder: bill '{bill_name}' (${amount}) due {due_date} for family {family_id}")


def get_reminder_sender() -> ReminderSender:
    return ConsoleReminderSender()
