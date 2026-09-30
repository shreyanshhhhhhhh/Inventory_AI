from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models import User
from app.schemas.auth import BusinessResponse
from app.services.auth import AuthError, current_business

router = APIRouter(prefix="/businesses", tags=["businesses"])


@router.get("/current", response_model=BusinessResponse)
def current_business_route(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessResponse:
    if user.business_id is None:
        raise HTTPException(status_code=403, detail="This account is not attached to a business.")
    try:
        return current_business(db, business_id=user.business_id)
    except AuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.message, "code": exc.code},
        ) from exc
