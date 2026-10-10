from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import require_onboarded
from app.db import get_db
from app.models import User
from app.schemas.reports import (
    AccountsBySupplierResponse,
    AccountsBySupplierRowResponse,
    AccountsSummaryResponse,
)
from app.services import reports as reports_service

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _require_business(user: User) -> str:
    if user.business_id is None:
        raise HTTPException(status_code=403, detail="This account is not attached to a business.")
    return user.business_id


@router.get("/summary", response_model=AccountsSummaryResponse)
def accounts_summary_route(
    user: User = Depends(require_onboarded),
    db: Session = Depends(get_db),
) -> AccountsSummaryResponse:
    business_id = _require_business(user)
    payload = reports_service.get_accounts_summary(db, business_id=business_id)
    return AccountsSummaryResponse.model_validate(payload)


@router.get("/by-supplier", response_model=AccountsBySupplierResponse)
def accounts_by_supplier_route(
    user: User = Depends(require_onboarded),
    db: Session = Depends(get_db),
) -> AccountsBySupplierResponse:
    business_id = _require_business(user)
    items = reports_service.get_accounts_by_supplier(db, business_id=business_id)
    return AccountsBySupplierResponse(
        items=[AccountsBySupplierRowResponse.model_validate(item) for item in items]
    )
