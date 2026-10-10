from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import require_onboarded
from app.db import get_db
from app.models import User
from app.schemas.reports import (
    ForecastDetailResponse,
    ForecastListResponse,
    MovementsOverTimeResponse,
    TopSellerResponse,
    TopSellersResponse,
)
from app.services import forecast as forecast_service
from app.services import reports as reports_service
from app.services.forecast import ForecastError

router = APIRouter(prefix="/insights", tags=["insights"])


def _require_business(user: User) -> str:
    if user.business_id is None:
        raise HTTPException(status_code=403, detail="This account is not attached to a business.")
    return user.business_id


def _handle_forecast_error(exc: ForecastError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"detail": exc.message, "code": exc.code},
    )


@router.get("/movements-over-time", response_model=MovementsOverTimeResponse)
def movements_over_time_route(
    user: User = Depends(require_onboarded),
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=1, le=366),
) -> MovementsOverTimeResponse:
    business_id = _require_business(user)
    payload = reports_service.get_movements_over_time(db, business_id=business_id, days=days)
    return MovementsOverTimeResponse.model_validate(payload)


@router.get("/top-sellers", response_model=TopSellersResponse)
def top_sellers_route(
    user: User = Depends(require_onboarded),
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


@router.get("/forecasts", response_model=ForecastListResponse)
def list_forecasts_route(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    history_days: int = Query(default=56, ge=7, le=180),
    horizon_days: int = Query(default=14, ge=1, le=30),
) -> ForecastListResponse:
    business_id = _require_business(user)
    payload = forecast_service.list_forecasts(
        db,
        business_id=business_id,
        history_days=history_days,
        horizon_days=horizon_days,
    )
    return ForecastListResponse.model_validate(payload)


@router.get("/forecasts/{product_id}", response_model=ForecastDetailResponse)
def get_forecast_route(
    product_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    history_days: int = Query(default=56, ge=7, le=180),
    horizon_days: int = Query(default=14, ge=1, le=30),
) -> ForecastDetailResponse:
    business_id = _require_business(user)
    try:
        payload = forecast_service.get_forecast(
            db,
            business_id=business_id,
            product_id=product_id,
            history_days=history_days,
            horizon_days=horizon_days,
        )
    except ForecastError as exc:
        raise _handle_forecast_error(exc) from exc
    return ForecastDetailResponse.model_validate(payload)
