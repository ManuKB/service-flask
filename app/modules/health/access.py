from app.models.family_membership import FamilyMembership
from app.models.patient import Patient
from app.modules.permissions.roles import FamilyRole


class HealthAccessError(Exception):
    """Raised when a member's role does not grant consent to view/edit a specific patient's data."""


# S5-03: "consent-aware access" is a step beyond require_active_member's
# family-wide check - Owner/Parent/Adult are trusted with every patient's
# records, while Child/Guest/Grandparent can only see a patient profile
# that is their own linked account (e.g. a Child role must not see a
# Parent's - or a sibling's - health data).
FULL_ACCESS_ROLES = {FamilyRole.OWNER, FamilyRole.PARENT, FamilyRole.ADULT}


def check_patient_access(membership: FamilyMembership, patient: Patient) -> None:
    if membership.role in FULL_ACCESS_ROLES:
        return
    if patient.linked_user_id is not None and patient.linked_user_id == membership.user_id:
        return
    raise HealthAccessError("Not authorized to access this patient's records")
