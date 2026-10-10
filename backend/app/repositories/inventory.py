from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.models import Location, Product, ProductSupplier, StockMovement, User


@dataclass(frozen=True)
class StockLevelRow:
    product_id: str
    location_id: str
    sku: str
    product_name: str
    location_name: str
    on_hand: Decimal
    reorder_point: Decimal | None


@dataclass(frozen=True)
class MovementHistoryRow:
    id: str
    occurred_at: datetime
    product_id: str
    product_name: str
    location_id: str
    location_name: str
    movement_type: str
    quantity: Decimal
    note: str | None
    reason: str | None
    created_by_user_id: str
    user_name: str


def list_locations(session: Session, business_id: str) -> list[Location]:
    return list(
        session.scalars(
            select(Location)
            .where(
                Location.business_id == business_id,
                Location.archived_at.is_(None),
            )
            .order_by(Location.is_default.desc(), Location.name.asc())
        )
    )


def get_location(session: Session, business_id: str, location_id: str) -> Location | None:
    return session.scalar(
        select(Location).where(
            Location.business_id == business_id,
            Location.id == location_id,
            Location.archived_at.is_(None),
        )
    )


def get_product(session: Session, business_id: str, product_id: str) -> Product | None:
    return session.scalar(
        select(Product).where(
            Product.business_id == business_id,
            Product.id == product_id,
            Product.archived_at.is_(None),
        )
    )


def get_on_hand(
    session: Session,
    *,
    business_id: str,
    product_id: str,
    location_id: str,
) -> Decimal:
    total = session.scalar(
        select(func.coalesce(func.sum(StockMovement.quantity), 0)).where(
            StockMovement.business_id == business_id,
            StockMovement.product_id == product_id,
            StockMovement.location_id == location_id,
        )
    )
    return Decimal(total or 0)


def get_stock_valuation(session: Session, *, business_id: str) -> tuple[Decimal, int]:
    """Return (value of stock with a preferred supplier cost, count of stocked products without one)."""
    preferred_cost = (
        select(
            ProductSupplier.product_id.label("product_id"),
            func.max(ProductSupplier.unit_cost).label("unit_cost"),
        )
        .where(
            ProductSupplier.business_id == business_id,
            ProductSupplier.is_preferred.is_(True),
        )
        .group_by(ProductSupplier.product_id)
        .subquery()
    )
    on_hand = (
        select(
            StockMovement.product_id.label("product_id"),
            func.sum(StockMovement.quantity).label("on_hand"),
        )
        .where(StockMovement.business_id == business_id)
        .group_by(StockMovement.product_id)
        .subquery()
    )
    row = session.execute(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (
                            preferred_cost.c.unit_cost.is_not(None),
                            on_hand.c.on_hand * preferred_cost.c.unit_cost,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("value"),
            func.coalesce(
                func.sum(case((preferred_cost.c.unit_cost.is_(None), 1), else_=0)),
                0,
            ).label("unvalued"),
        )
        .select_from(on_hand)
        .join(Product, Product.id == on_hand.c.product_id)
        .outerjoin(preferred_cost, preferred_cost.c.product_id == on_hand.c.product_id)
        .where(
            Product.business_id == business_id,
            Product.archived_at.is_(None),
            on_hand.c.on_hand > 0,
        )
    ).one()
    return Decimal(row.value or 0), int(row.unvalued or 0)


def insert_movement(session: Session, movement: StockMovement) -> StockMovement:
    session.add(movement)
    session.flush()
    return movement


def get_received_quantity(
    session: Session,
    *,
    business_id: str,
    purchase_order_item_id: str,
) -> Decimal:
    total = session.scalar(
        select(func.coalesce(func.sum(StockMovement.quantity), 0)).where(
            StockMovement.business_id == business_id,
            StockMovement.purchase_order_item_id == purchase_order_item_id,
            StockMovement.movement_type == "purchase_receipt",
        )
    )
    return Decimal(total or 0)


def list_stock_levels(
    session: Session,
    *,
    business_id: str,
    search: str | None,
    location_id: str | None,
    low_only: bool,
    page: int,
    page_size: int,
) -> tuple[list[StockLevelRow], int]:
    on_hand = (
        select(
            StockMovement.business_id.label("business_id"),
            StockMovement.product_id.label("product_id"),
            StockMovement.location_id.label("location_id"),
            func.sum(StockMovement.quantity).label("on_hand"),
        )
        .where(StockMovement.business_id == business_id)
        .group_by(
            StockMovement.business_id,
            StockMovement.product_id,
            StockMovement.location_id,
        )
        .subquery()
    )

    stmt = (
        select(
            on_hand.c.product_id,
            on_hand.c.location_id,
            Product.sku,
            Product.name.label("product_name"),
            Location.name.label("location_name"),
            on_hand.c.on_hand,
            Product.reorder_point,
        )
        .join(Product, Product.id == on_hand.c.product_id)
        .join(Location, Location.id == on_hand.c.location_id)
        .where(on_hand.c.business_id == business_id)
    )

    if location_id:
        stmt = stmt.where(on_hand.c.location_id == location_id)

    if search:
        pattern = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Product.name).like(pattern),
                func.lower(Product.sku).like(pattern),
            )
        )

    if low_only:
        stmt = stmt.where(
            or_(
                on_hand.c.on_hand <= 0,
                (
                    Product.reorder_point.is_not(None)
                    & (on_hand.c.on_hand <= Product.reorder_point)
                ),
            )
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int(session.scalar(count_stmt) or 0)

    rows = session.execute(
        stmt.order_by(Product.name.asc(), Location.name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        StockLevelRow(
            product_id=row.product_id,
            location_id=row.location_id,
            sku=row.sku,
            product_name=row.product_name,
            location_name=row.location_name,
            on_hand=Decimal(row.on_hand),
            reorder_point=Decimal(row.reorder_point) if row.reorder_point is not None else None,
        )
        for row in rows
    ]
    return items, total


def list_movements(
    session: Session,
    *,
    business_id: str,
    movement_type: str | None,
    product_id: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    page: int,
    page_size: int,
) -> tuple[list[MovementHistoryRow], int]:
    stmt = (
        select(
            StockMovement.id,
            StockMovement.occurred_at,
            StockMovement.product_id,
            Product.name.label("product_name"),
            StockMovement.location_id,
            Location.name.label("location_name"),
            StockMovement.movement_type,
            StockMovement.quantity,
            StockMovement.note,
            StockMovement.reason,
            StockMovement.created_by_user_id,
            User.full_name.label("user_name"),
        )
        .join(Product, Product.id == StockMovement.product_id)
        .join(Location, Location.id == StockMovement.location_id)
        .join(User, User.id == StockMovement.created_by_user_id)
        .where(StockMovement.business_id == business_id)
    )

    if movement_type:
        stmt = stmt.where(StockMovement.movement_type == movement_type)

    if product_id:
        stmt = stmt.where(StockMovement.product_id == product_id)

    if date_from:
        stmt = stmt.where(StockMovement.occurred_at >= date_from)

    if date_to:
        stmt = stmt.where(StockMovement.occurred_at <= date_to)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int(session.scalar(count_stmt) or 0)

    rows = session.execute(
        stmt.order_by(StockMovement.occurred_at.desc(), StockMovement.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        MovementHistoryRow(
            id=row.id,
            occurred_at=row.occurred_at,
            product_id=row.product_id,
            product_name=row.product_name,
            location_id=row.location_id,
            location_name=row.location_name,
            movement_type=row.movement_type,
            quantity=Decimal(row.quantity),
            note=row.note,
            reason=row.reason,
            created_by_user_id=row.created_by_user_id,
            user_name=row.user_name,
        )
        for row in rows
    ]
    return items, total
