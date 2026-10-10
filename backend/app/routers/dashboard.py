from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import require_onboarded
from app.db import get_db
from app.models import User
from app.schemas.dashboard import (
    DashboardActivityItemResponse,
    DashboardActivityResponse,
    DashboardSummaryResponse,
    NeedsAttentionItemResponse,
    NeedsAttentionResponse,
)
from app.services import dashboard as dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _require_business(user: User) -> str:
    if user.business_id is None:
        raise HTTPException(status_code=403, detail="This account is not attached to a business.")
    return user.business_id


@router.get("/summary", response_model=DashboardSummaryResponse)
def dashboard_summary_route(
    user: User = Depends(require_onboarded),
    db: Session = Depends(get_db),
) -> DashboardSummaryResponse:
    business_id = _require_business(user)
    payload = dashboard_service.get_summary(db, business_id=business_id)
    return DashboardSummaryResponse.model_validate(payload)


@router.get("/needs-attention", response_model=NeedsAttentionResponse)
def dashboard_needs_attention_route(
    user: User = Depends(require_onboarded),
    db: Session = Depends(get_db),
) -> NeedsAttentionResponse:
    business_id = _require_business(user)
    items = dashboard_service.get_needs_attention(db, business_id=business_id)
    return NeedsAttentionResponse(
        items=[NeedsAttentionItemResponse.model_validate(item) for item in items]
    )


@router.get("/activity", response_model=DashboardActivityResponse)
def dashboard_activity_route(
    user: User = Depends(require_onboarded),
    db: Session = Depends(get_db),
) -> DashboardActivityResponse:
    business_id = _require_business(user)
    items = dashboard_service.get_activity(db, business_id=business_id, limit=10)
    return DashboardActivityResponse(
        items=[DashboardActivityItemResponse.model_validate(item) for item in items]
    )
