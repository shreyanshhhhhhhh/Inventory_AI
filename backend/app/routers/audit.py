from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import require_owner
from app.db import get_db
from app.models import User
from app.schemas.audit import AuditEntryResponse, AuditLogResponse
from app.services.audit import list_audit_log

router = APIRouter(prefix="/audit-log", tags=["audit"])


@router.get("", response_model=AuditLogResponse)
def list_audit_log_route(
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> AuditLogResponse:
    if user.business_id is None:
        raise HTTPException(status_code=403, detail="This account is not attached to a business.")
    items, total = list_audit_log(
        db,
        business_id=user.business_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        page=page,
        page_size=page_size,
    )
    return AuditLogResponse(
        items=[AuditEntryResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
