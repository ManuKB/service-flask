import uuid

from flask import Blueprint

from app.core.database import get_db
from app.core.responses import envelope_list
from app.modules.audit import service
from app.modules.audit.permissions import require_family_member
from app.schemas.audit_event import AuditEventResponse

bp = Blueprint("audit", __name__, url_prefix="/families")


@bp.get("/<uuid:family_id>/audit")
def get_family_audit_log(family_id: uuid.UUID):
    require_family_member(family_id)
    events = service.list_events_for_family(get_db(), family_id)
    return envelope_list([AuditEventResponse.model_validate(e) for e in events])
