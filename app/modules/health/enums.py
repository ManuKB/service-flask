import enum


class MedicalRecordType(str, enum.Enum):
    DIAGNOSIS = "diagnosis"
    LAB_RESULT = "lab_result"
    VACCINATION = "vaccination"
    PRESCRIPTION = "prescription"
    OTHER = "other"


# S5-04: "Attachment accepts approved file types" - checked against the
# attachment_url's extension, same pattern as any upload allowlist.
ALLOWED_ATTACHMENT_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
