from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Product, ProductSupplier, PurchaseOrder, PurchaseOrderItem, StockMovement, Supplier
from app.services.forecast import list_forecasts

_OPEN_PO_STATUSES = ("draft", "approved", "sent")


def reorder_recommendations(
    session: Session,
    *,
    business_id: str,
) -> list[dict[str, object]]:
    on_hand_rows = session.execute(
        select(
            StockMovement.product_id,
            func.coalesce(func.sum(StockMovement.quantity), 0).label("on_hand"),
        )
        .where(StockMovement.business_id == business_id)
        .group_by(StockMovement.product_id)
    ).all()
    on_hand_by_product = {
        row.product_id: Decimal(row.on_hand) for row in on_hand_rows
    }
    forecasts = list_forecasts(session, business_id=business_id)
    forecast_by_product = {
        item["product_id"]: Decimal(str(item["forecast_units"]))
        for item in forecasts["items"]
    }
    products = session.scalars(
        select(Product)
        .where(Product.business_id == business_id, Product.archived_at.is_(None))
        .order_by(Product.name.asc())
    ).all()
    suppliers_by_product = _supplier_options(session, business_id, [product.id for product in products])

    recommendations: list[dict[str, object]] = []
    for product in products:
        on_hand = on_hand_by_product.get(product.id, Decimal("0"))
        forecast_units = forecast_by_product.get(product.id, Decimal("0"))
        reorder_point = product.reorder_point or Decimal("0")
        safety_stock = product.safety_stock or Decimal("0")
        needed = max(reorder_point, forecast_units) + safety_stock
        if on_hand >= needed:
            continue
        recommendations.append(
            {
                "product_id": product.id,
                "sku": product.sku,
                "product_name": product.name,
                "on_hand": on_hand,
                "reorder_point": product.reorder_point,
                "safety_stock": product.safety_stock,
                "forecast_units": forecast_units,
                "recommended_quantity": needed - on_hand,
                "suppliers": suppliers_by_product.get(product.id, []),
            }
        )
    return recommendations


def list_open_purchase_orders(
    session: Session,
    *,
    business_id: str,
) -> list[dict[str, object]]:
    orders = session.scalars(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.business_id == business_id,
            PurchaseOrder.status.in_(_OPEN_PO_STATUSES),
        )
        .order_by(PurchaseOrder.created_at.asc())
    ).all()
    if not orders:
        return []
    order_ids = [order.id for order in orders]
    item_rows = session.scalars(
        select(PurchaseOrderItem).where(
            PurchaseOrderItem.business_id == business_id,
            PurchaseOrderItem.purchase_order_id.in_(order_ids),
        )
    ).all()
    lines_by_order: dict[str, list[dict[str, object]]] = {}
    for item in item_rows:
        lines_by_order.setdefault(item.purchase_order_id, []).append(
            {
                "product_id": item.product_id,
                "quantity_ordered": item.quantity_ordered,
            }
        )
    return [
        {
            "id": order.id,
            "po_number": order.po_number,
            "supplier_id": order.supplier_id,
            "status": order.status,
            "lines": lines_by_order.get(order.id, []),
        }
        for order in orders
    ]


def _supplier_options(
    session: Session,
    business_id: str,
    product_ids: list[str],
) -> dict[str, list[dict[str, object]]]:
    if not product_ids:
        return {}
    links = session.scalars(
        select(ProductSupplier).where(
            ProductSupplier.business_id == business_id,
            ProductSupplier.product_id.in_(product_ids),
        )
    ).all()
    supplier_ids = {link.supplier_id for link in links}
    if not supplier_ids:
        return {}
    suppliers = session.scalars(
        select(Supplier).where(
            Supplier.business_id == business_id,
            Supplier.id.in_(supplier_ids),
        )
    ).all()
    supplier_by_id = {row.id: row for row in suppliers}
    grouped: dict[str, list[dict[str, object]]] = {}
    for link in links:
        supplier = supplier_by_id.get(link.supplier_id)
        if supplier is None:
            continue
        grouped.setdefault(link.product_id, []).append(
            {
                "supplier_id": link.supplier_id,
                "supplier_name": supplier.name,
                "unit_cost": link.unit_cost,
                "lead_time_days": link.lead_time_days,
                "is_preferred": link.is_preferred,
                "is_active": supplier.archived_at is None,
            }
        )
    for options in grouped.values():
        options.sort(key=lambda item: (not bool(item["is_preferred"]), str(item["supplier_name"])))
    return grouped
