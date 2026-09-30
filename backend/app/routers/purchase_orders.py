from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models import User
from app.schemas.purchase_orders import (
    PurchaseOrderCreateRequest,
    PurchaseOrderListResponse,
    PurchaseOrderResponse,
    PurchaseOrderTransitionRequest,
    PurchaseOrderUpdateRequest,
)
from app.services import purchase_orders as po_service
from app.services.purchase_orders import PurchaseOrderError

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])


def _require_business(user: User) -> str:
    if user.business_id is None:
        raise HTTPException(status_code=403, detail="This account is not attached to a business.")
    return user.business_id


def _handle_po_error(exc: PurchaseOrderError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"detail": exc.message, "code": exc.code},
    )


@router.post("", response_model=PurchaseOrderResponse, status_code=201)
def create_po_route(
    body: PurchaseOrderCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    business_id = _require_business(user)
    try:
        order = po_service.create_po(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            supplier_id=body.supplier_id,
            expected_date=body.expected_date,
            location_id=body.location_id,
            notes=body.notes,
            line_items=[
                {
                    "product_id": line.product_id,
                    "quantity": line.quantity,
                    "unit_cost": line.unit_cost,
                }
                for line in body.line_items
            ],
        )
    except PurchaseOrderError as exc:
        raise _handle_po_error(exc) from exc
    return PurchaseOrderResponse.model_validate(order)


@router.get("", response_model=PurchaseOrderListResponse)
def list_pos_route(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: str | None = Query(default=None),
    supplier_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> PurchaseOrderListResponse:
    business_id = _require_business(user)
    items, total = po_service.list_pos(
        db,
        business_id=business_id,
        status=status.strip().lower() if status else None,
        supplier_id=supplier_id,
        page=page,
        page_size=page_size,
    )
    return PurchaseOrderListResponse(
        items=[PurchaseOrderResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{purchase_order_id}", response_model=PurchaseOrderResponse)
def get_po_route(
    purchase_order_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    business_id = _require_business(user)
    try:
        order = po_service.get_po(
            db,
            business_id=business_id,
            purchase_order_id=purchase_order_id,
        )
    except PurchaseOrderError as exc:
        raise _handle_po_error(exc) from exc
    return PurchaseOrderResponse.model_validate(order)


@router.patch("/{purchase_order_id}", response_model=PurchaseOrderResponse)
def update_po_route(
    purchase_order_id: str,
    body: PurchaseOrderUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    business_id = _require_business(user)
    try:
        order = po_service.update_po(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            purchase_order_id=purchase_order_id,
            supplier_id=body.supplier_id,
            expected_date=body.expected_date,
            location_id=body.location_id,
            notes=body.notes,
            line_items=[
                {
                    "product_id": line.product_id,
                    "quantity": line.quantity,
                    "unit_cost": line.unit_cost,
                }
                for line in body.line_items
            ]
            if body.line_items is not None
            else None,
        )
    except PurchaseOrderError as exc:
        raise _handle_po_error(exc) from exc
    return PurchaseOrderResponse.model_validate(order)


@router.post("/{purchase_order_id}/transition", response_model=PurchaseOrderResponse)
def transition_po_route(
    purchase_order_id: str,
    body: PurchaseOrderTransitionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    business_id = _require_business(user)
    try:
        order = po_service.transition_po(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            purchase_order_id=purchase_order_id,
            action=body.action,
            actor_role=user.role or "",
        )
    except PurchaseOrderError as exc:
        raise _handle_po_error(exc) from exc
    return PurchaseOrderResponse.model_validate(order)
