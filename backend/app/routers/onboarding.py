from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_owner
from app.db import get_db
from app.models import User
from app.schemas.imports import DemoSeedResponse
from app.services.demo_seed import DemoSeedError, load_demo_data

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _require_business(user: User) -> str:
    if user.business_id is None:
        raise HTTPException(status_code=403, detail="This account is not attached to a business.")
    return user.business_id


@router.post("/load-demo-data", response_model=DemoSeedResponse)
def load_demo_data_route(
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> DemoSeedResponse:
    business_id = _require_business(user)
    try:
        result = load_demo_data(
            db,
            business_id=business_id,
            actor_user_id=user.id,
        )
    except DemoSeedError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.message, "code": exc.code},
        ) from exc
    return DemoSeedResponse.model_validate(result)
