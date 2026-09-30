from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models import User
from app.schemas.inventory import (
    LocationResponse,
    MovementCreateRequest,
    MovementListResponse,
    MovementResponse,
    StockListResponse,
    StockLevelResponse,
)
from app.services import inventory as inventory_service
from app.services.inventory import InventoryError

router = APIRouter(prefix="/inventory", tags=["inventory"])


def _require_business(user: User) -> str:
    if user.business_id is None:
        raise HTTPException(status_code=403, detail="This account is not attached to a business.")
    return user.business_id


def _handle_inventory_error(exc: InventoryError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"detail": exc.message, "code": exc.code},
    )


@router.get("/locations", response_model=list[LocationResponse])
def list_locations_route(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LocationResponse]:
    business_id = _require_business(user)
    rows = inventory_service.list_locations(db, business_id=business_id)
    return [LocationResponse.model_validate(row) for row in rows]


@router.get("/stock", response_model=StockListResponse)
def list_stock_route(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    search: str | None = Query(default=None),
    location_id: str | None = Query(default=None),
    low_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> StockListResponse:
    business_id = _require_business(user)
    items, total = inventory_service.get_stock_levels(
        db,
        business_id=business_id,
        search=search,
        location_id=location_id,
        low_only=low_only,
        page=page,
        page_size=page_size,
    )
    return StockListResponse(
        items=[StockLevelResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/movements", response_model=MovementListResponse)
def list_movements_route(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    type: str | None = Query(default=None, alias="type"),
    product_id: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> MovementListResponse:
    business_id = _require_business(user)
    movement_type = type.strip().lower() if type else None
    items, total = inventory_service.get_movement_history(
        db,
        business_id=business_id,
        movement_type=movement_type,
        product_id=product_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return MovementListResponse(
        items=[MovementResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/movements", response_model=MovementResponse, status_code=201)
def create_movement_route(
    body: MovementCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MovementResponse:
    business_id = _require_business(user)
    try:
        movement = inventory_service.record_movement(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            product_id=body.product_id,
            location_id=body.location_id,
            movement_type=body.type,
            quantity=body.quantity,
            note=body.note,
            destination_location_id=body.destination_location_id,
        )
    except InventoryError as exc:
        raise _handle_inventory_error(exc) from exc
    return MovementResponse.model_validate(movement)
