from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.db import get_db
from app.models import User
from app.schemas.jobs import ExceptionScanJobRequest, ExceptionScanJobResponse
from app.services.jobs import run_exception_scans

router = APIRouter(prefix="/jobs", tags=["jobs"])
_bearer = HTTPBearer(auto_error=False)


@router.post("/exception-scan", response_model=ExceptionScanJobResponse)
def exception_scan_job(
    body: ExceptionScanJobRequest | None = None,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_job_secret: str | None = Header(default=None, alias="X-Job-Secret"),
) -> ExceptionScanJobResponse:
    payload = body or ExceptionScanJobRequest()
    secret_ok = bool(
        settings.job_secret and x_job_secret and x_job_secret == settings.job_secret
    )
    if secret_ok:
        result = run_exception_scans(
            db,
            business_id=payload.business_id,
            actor_user_id=None,
            force=payload.force,
            respect_hour=not payload.force,
        )
        db.commit()
        return ExceptionScanJobResponse.model_validate(result)

    if credentials is None:
        raise HTTPException(status_code=401, detail="Sign in is required.")
    user = _owner_from_bearer(credentials, db)
    result = run_exception_scans(
        db,
        business_id=user.business_id,
        actor_user_id=user.id,
        force=True,
        respect_hour=False,
    )
    db.commit()
    return ExceptionScanJobResponse.model_validate(result)


def _owner_from_bearer(credentials: HTTPAuthorizationCredentials, db: Session) -> User:
    user = get_current_user(credentials, db)
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Owner access is required.")
    if user.business_id is None:
        raise HTTPException(status_code=400, detail="Business is required.")
    return user
