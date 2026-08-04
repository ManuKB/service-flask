from app.modules.health.enums import ALLOWED_ATTACHMENT_EXTENSIONS


class AttachmentTypeError(Exception):
    """Raised when an attachment_url's extension is not on the approved allowlist."""


def validate_attachment_url(attachment_url: str | None) -> None:
    if attachment_url is None:
        return
    extension = attachment_url.rsplit(".", 1)[-1].lower() if "." in attachment_url else ""
    if extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_ATTACHMENT_EXTENSIONS))
        raise AttachmentTypeError(f"Attachment type not allowed - accepted types: {allowed}")
