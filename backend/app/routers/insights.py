from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models import User
from app.schemas.reports import (
    MovementsOverTimeResponse,
    TopSellerResponse,
    TopSellersResponse,
)
from app.services import reports as reports_service

router = APIRouter(prefix="/insights", tags=["insights"])


def _require_business(user: User) -> str:
    if user.business_id is None:
        raise HTTPException(status_code=403, detail="This account is not attached to a business.")
    return user.business_id


@router.get("/movements-over-time", response_model=MovementsOverTimeResponse)
def movements_over_time_route(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=1, le=366),
) -> MovementsOverTimeResponse:
    business_id = _require_business(user)
    payload = reports_service.get_movements_over_time(db, business_id=business_id, days=days)
    return MovementsOverTimeResponse.model_validate(payload)


@router.get("/top-sellers", response_model=TopSellersResponse)
def top_sellers_route(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=1, le=366),
    limit: int = Query(default=5, ge=1, le=25),
) -> TopSellersResponse:
    business_id = _require_business(user)
    payload = reports_service.get_top_sellers(
        db,
        business_id=business_id,
        days=days,
        limit=limit,
    )
    return TopSellersResponse(
        days=payload["days"],
        limit=payload["limit"],
        items=[TopSellerResponse.model_validate(item) for item in payload["items"]],
    )
