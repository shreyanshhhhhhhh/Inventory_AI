from decimal import Decimal

from sqlalchemy import String, case, cast, func, literal, or_, select, union_all
from sqlalchemy.orm import Session

from app.models import AuditLog, Location, Product, PurchaseOrder, StockMovement
from app.services.inventory import compute_stock_status

PO_STATUS_ACTIONS = (
    "purchase_order.approve",
    "purchase_order.send",
    "purchase_order.receive",
    "purchase_order.cancel",
)

PO_ACTION_LABELS = {
    "purchase_order.approve": "Approved",
    "purchase_order.send": "Sent",
    "purchase_order.receive": "Received",
    "purchase_order.cancel": "Cancelled",
}


def _on_hand_subquery(business_id: str):
    return (
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


def _low_stock_predicate(on_hand_column, reorder_point_column):
    return or_(
        on_hand_column <= 0,
        (
            reorder_point_column.is_not(None)
            & (on_hand_column <= reorder_point_column)
        ),
    )


def get_summary(session: Session, *, business_id: str) -> dict[str, object]:
    on_hand = _on_hand_subquery(business_id)

    total_stock_value = session.scalar(
        select(
            func.coalesce(
                func.sum(on_hand.c.on_hand * func.coalesce(Product.cost, 0)),
                0,
            )
        )
        .select_from(on_hand)
        .join(Product, Product.id == on_hand.c.product_id)
        .where(
            on_hand.c.business_id == business_id,
            Product.archived_at.is_(None),
        )
    )

    low_stock_count = session.scalar(
        select(func.count())
        .select_from(on_hand)
        .join(Product, Product.id == on_hand.c.product_id)
        .where(
            on_hand.c.business_id == business_id,
            Product.archived_at.is_(None),
            _low_stock_predicate(on_hand.c.on_hand, Product.reorder_point),
        )
    )

    open_purchase_orders = session.scalar(
        select(func.count())
        .select_from(PurchaseOrder)
        .where(
            PurchaseOrder.business_id == business_id,
            PurchaseOrder.status.in_(("draft", "approved", "sent")),
        )
    )

    return {
        "total_stock_value": Decimal(total_stock_value or 0),
        "low_stock_count": int(low_stock_count or 0),
        "open_purchase_orders": int(open_purchase_orders or 0),
        "pending_approvals": 0,
        "open_exceptions": 0,
    }


def get_needs_attention(session: Session, *, business_id: str) -> list[dict[str, object]]:
    on_hand = _on_hand_subquery(business_id)

    rows = session.execute(
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
        .where(
            on_hand.c.business_id == business_id,
            Product.archived_at.is_(None),
            _low_stock_predicate(on_hand.c.on_hand, Product.reorder_point),
        )
        .order_by(
            case((on_hand.c.on_hand <= 0, 0), else_=1),
            on_hand.c.on_hand.asc(),
            Product.name.asc(),
            Location.name.asc(),
        )
    ).all()

    items: list[dict[str, object]] = []
    for row in rows:
        on_hand_value = Decimal(row.on_hand)
        reorder_point = (
            Decimal(row.reorder_point) if row.reorder_point is not None else None
        )
        items.append(
            {
                "product_id": row.product_id,
                "location_id": row.location_id,
                "sku": row.sku,
                "product_name": row.product_name,
                "location_name": row.location_name,
                "on_hand": on_hand_value,
                "reorder_point": reorder_point,
                "status": compute_stock_status(on_hand_value, reorder_point),
            }
        )
    return items


def get_activity(session: Session, *, business_id: str, limit: int = 10) -> list[dict[str, object]]:
    movement_events = (
        select(
            StockMovement.id.label("id"),
            literal("movement").label("kind"),
            StockMovement.occurred_at.label("occurred_at"),
            Product.name.label("title"),
            StockMovement.movement_type.label("movement_type"),
            StockMovement.quantity.label("quantity"),
            cast(literal(None), String).label("action"),
        )
        .join(Product, Product.id == StockMovement.product_id)
        .where(
            StockMovement.business_id == business_id,
            Product.archived_at.is_(None),
        )
    )

    po_events = (
        select(
            AuditLog.id.label("id"),
            literal("purchase_order_status").label("kind"),
            AuditLog.created_at.label("occurred_at"),
            PurchaseOrder.po_number.label("title"),
            cast(literal(None), String).label("movement_type"),
            cast(literal(None), StockMovement.quantity.type).label("quantity"),
            AuditLog.action.label("action"),
        )
        .join(PurchaseOrder, PurchaseOrder.id == AuditLog.entity_id)
        .where(
            AuditLog.business_id == business_id,
            AuditLog.entity_type == "purchase_order",
            AuditLog.action.in_(PO_STATUS_ACTIONS),
            PurchaseOrder.business_id == business_id,
        )
    )

    combined = union_all(movement_events, po_events).subquery()
    rows = session.execute(
        select(combined)
        .order_by(combined.c.occurred_at.desc(), combined.c.id.desc())
        .limit(limit)
    ).all()

    items: list[dict[str, object]] = []
    for row in rows:
        if row.kind == "movement":
            subtitle = row.movement_type.replace("_", " ")
            items.append(
                {
                    "id": row.id,
                    "kind": "movement",
                    "occurred_at": row.occurred_at,
                    "title": row.title,
                    "subtitle": subtitle,
                    "quantity": Decimal(row.quantity),
                }
            )
        else:
            label = PO_ACTION_LABELS.get(row.action, row.action)
            items.append(
                {
                    "id": row.id,
                    "kind": "purchase_order_status",
                    "occurred_at": row.occurred_at,
                    "title": row.title,
                    "subtitle": label,
                    "quantity": None,
                }
            )
    return items
