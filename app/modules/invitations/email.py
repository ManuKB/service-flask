from abc import ABC, abstractmethod


class EmailSender(ABC):
    """Pluggable delivery hook. Swap the MVP console implementation for a
    real SMTP/SES/Postmark adapter without touching callers."""

    @abstractmethod
    def send_invitation_email(self, to_email: str, family_name: str, invite_link: str) -> None: ...

    @abstractmethod
    def send_password_setup_email(self, to_email: str, family_name: str, setup_link: str) -> None: ...


class ConsoleEmailSender(EmailSender):
    """MVP stub - logs the invite link instead of sending real email."""

    def send_invitation_email(self, to_email: str, family_name: str, invite_link: str) -> None:
        print(f"[invitations] would email {to_email}: join '{family_name}' -> {invite_link}")

    def send_password_setup_email(self, to_email: str, family_name: str, setup_link: str) -> None:
        print(f"[invitations] would email {to_email}: set your password for '{family_name}' -> {setup_link}")


def get_email_sender() -> EmailSender:
    return ConsoleEmailSender()
