from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.db import get_db
from app.models import User
from app.schemas.supplier_messages import SupplierReplyCreateRequest, SupplierReplyResponse
from app.services.supplier_messages import SupplierMessageError, record_reply

router = APIRouter(prefix="/supplier-replies", tags=["supplier-replies"])
_bearer = HTTPBearer(auto_error=False)


@router.post("", response_model=SupplierReplyResponse, status_code=201)
def create_supplier_reply(
    body: SupplierReplyCreateRequest,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_job_secret: str | None = Header(default=None, alias="X-Job-Secret"),
) -> SupplierReplyResponse:
    secret_ok = bool(settings.job_secret and x_job_secret and x_job_secret == settings.job_secret)
    actor_user_id: str | None = None
    if secret_ok:
        if not body.business_id:
            raise AppError("business_id is required for a webhook reply.", code="bad_request")
        business_id = body.business_id
    else:
        if credentials is None:
            raise HTTPException(status_code=401, detail="Sign in is required.")
        user = get_current_user(credentials, db)
        if user.business_id is None:
            raise AppError("This account is not attached to a business.", code="forbidden", status_code=403)
        business_id = user.business_id
        actor_user_id = user.id
    try:
        row = record_reply(
            db,
            business_id=business_id,
            actor_user_id=actor_user_id,
            message_id=body.message_id,
            thread_id=body.thread_id,
            body=body.body,
        )
    except SupplierMessageError as exc:
        raise AppError(exc.message, code=exc.code, status_code=exc.status_code) from exc
    return SupplierReplyResponse.model_validate(row)
