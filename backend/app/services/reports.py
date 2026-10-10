from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Product, PurchaseOrder, PurchaseOrderItem, StockMovement, Supplier
from app.models.types import utcnow
from app.repositories import inventory as inventory_repo

IN_MOVEMENT_TYPES = ("receipt", "purchase_receipt")
OPEN_PO_STATUSES = ("draft", "approved", "sent")
PAYABLE_PO_STATUSES = ("approved", "sent")


def _movement_window(*, days: int) -> tuple[datetime, datetime, list[date]]:
    if days < 1:
        raise ValueError("days must be at least 1")
    today = utcnow().astimezone(timezone.utc).date()
    start_day = today - timedelta(days=days - 1)
    start = datetime.combine(start_day, time.min, tzinfo=timezone.utc)
    end = datetime.combine(today, time.max, tzinfo=timezone.utc)
    day_list = [start_day + timedelta(days=offset) for offset in range(days)]
    return start, end, day_list


def get_movements_over_time(
    session: Session,
    *,
    business_id: str,
    days: int,
) -> dict[str, object]:
    start, end, day_list = _movement_window(days=days)
    movement_day = func.date(StockMovement.occurred_at)

    rows = session.execute(
        select(
            movement_day.label("day"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            StockMovement.movement_type.in_(IN_MOVEMENT_TYPES),
                            StockMovement.quantity,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("units_in"),
            func.coalesce(
                func.sum(
                    case(
                        (StockMovement.movement_type == "sale", -StockMovement.quantity),
                        else_=0,
                    )
                ),
                0,
            ).label("units_out"),
        )
        .where(
            StockMovement.business_id == business_id,
            StockMovement.occurred_at >= start,
            StockMovement.occurred_at <= end,
        )
        .group_by(movement_day)
    ).all()

    totals_by_day: dict[date, tuple[Decimal, Decimal]] = {}
    for row in rows:
        day_value = row.day
        if isinstance(day_value, str):
            day_key = date.fromisoformat(day_value)
        else:
            day_key = day_value
        totals_by_day[day_key] = (Decimal(row.units_in), Decimal(row.units_out))

    items = [
        {
            "date": day,
            "units_in": totals_by_day.get(day, (Decimal("0"), Decimal("0")))[0],
            "units_out": totals_by_day.get(day, (Decimal("0"), Decimal("0")))[1],
        }
        for day in day_list
    ]
    return {"days": days, "items": items}


def get_top_sellers(
    session: Session,
    *,
    business_id: str,
    days: int,
    limit: int,
) -> dict[str, object]:
    start, end, _ = _movement_window(days=days)

    rows = session.execute(
        select(
            Product.id.label("product_id"),
            Product.name.label("product_name"),
            func.coalesce(func.sum(-StockMovement.quantity), 0).label("units_sold"),
        )
        .join(Product, Product.id == StockMovement.product_id)
        .where(
            StockMovement.business_id == business_id,
            Product.business_id == business_id,
            Product.archived_at.is_(None),
            StockMovement.movement_type == "sale",
            StockMovement.occurred_at >= start,
            StockMovement.occurred_at <= end,
        )
        .group_by(Product.id, Product.name)
        .order_by(func.sum(-StockMovement.quantity).desc(), Product.name.asc())
        .limit(limit)
    ).all()

    items = [
        {
            "product_id": row.product_id,
            "product_name": row.product_name,
            "units_sold": Decimal(row.units_sold),
        }
        for row in rows
        if Decimal(row.units_sold) > 0
    ]
    return {"days": days, "limit": limit, "items": items}


def _sum_po_value(session: Session, *, business_id: str, statuses: tuple[str, ...]) -> Decimal:
    total = session.scalar(
        select(
            func.coalesce(
                func.sum(PurchaseOrderItem.quantity_ordered * PurchaseOrderItem.unit_cost),
                0,
            )
        )
        .select_from(PurchaseOrderItem)
        .join(
            PurchaseOrder,
            PurchaseOrder.id == PurchaseOrderItem.purchase_order_id,
        )
        .where(
            PurchaseOrder.business_id == business_id,
            PurchaseOrderItem.business_id == business_id,
            PurchaseOrder.status.in_(statuses),
        )
    )
    return Decimal(total or 0)


def get_accounts_summary(session: Session, *, business_id: str) -> dict[str, object]:
    stock_value, unvalued_product_count = inventory_repo.get_stock_valuation(
        session, business_id=business_id
    )

    return {
        "stock_value": stock_value,
        "unvalued_product_count": unvalued_product_count,
        "open_po_value": _sum_po_value(session, business_id=business_id, statuses=OPEN_PO_STATUSES),
        "payables_due": _sum_po_value(
            session,
            business_id=business_id,
            statuses=PAYABLE_PO_STATUSES,
        ),
    }


def get_accounts_by_supplier(session: Session, *, business_id: str) -> list[dict[str, object]]:
    rows = session.execute(
        select(
            Supplier.id.label("supplier_id"),
            Supplier.name.label("supplier_name"),
            PurchaseOrder.status.label("status"),
            func.coalesce(
                func.sum(PurchaseOrderItem.quantity_ordered * PurchaseOrderItem.unit_cost),
                0,
            ).label("total"),
            func.count(func.distinct(PurchaseOrder.id)).label("purchase_order_count"),
        )
        .select_from(PurchaseOrderItem)
        .join(
            PurchaseOrder,
            PurchaseOrder.id == PurchaseOrderItem.purchase_order_id,
        )
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .where(
            PurchaseOrder.business_id == business_id,
            PurchaseOrderItem.business_id == business_id,
            Supplier.business_id == business_id,
        )
        .group_by(Supplier.id, Supplier.name, PurchaseOrder.status)
        .order_by(Supplier.name.asc(), PurchaseOrder.status.asc())
    ).all()

    return [
        {
            "supplier_id": row.supplier_id,
            "supplier_name": row.supplier_name,
            "status": row.status,
            "total": Decimal(row.total),
            "purchase_order_count": int(row.purchase_order_count),
        }
        for row in rows
        if Decimal(row.total) > 0
    ]
