from datetime import date, timedelta
from decimal import Decimal, ROUND_FLOOR

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Product, ProductSupplier, PurchaseOrder, PurchaseOrderItem, StockMovement, Supplier
from app.models.types import utcnow
from app.services.forecast import list_forecasts

_OPEN_PO_STATUSES = ("draft", "approved", "sent")
_ZERO = Decimal("0")


def reorder_recommendations(
    session: Session,
    *,
    business_id: str,
) -> list[dict[str, object]]:
    return [
        row
        for row in _recommendation_rows(session, business_id=business_id)
        if Decimal(str(row["recommended_quantity"])) > 0
    ]


def whatif_compare(
    session: Session,
    *,
    business_id: str,
    demand_pct: Decimal | None = None,
    delay_days: int | None = None,
    lead_time_days: int | None = None,
    product_id: str | None = None,
) -> dict[str, object]:
    """Recompute reorder metrics with modified inputs. No LLM arithmetic."""
    today = utcnow().astimezone().date()
    before_rows = _recommendation_rows(session, business_id=business_id)
    after_rows = _recommendation_rows(
        session,
        business_id=business_id,
        demand_pct=demand_pct,
        delay_days=delay_days,
        lead_time_days=lead_time_days,
    )
    if product_id:
        before_rows = [row for row in before_rows if row["product_id"] == product_id]
        after_rows = [row for row in after_rows if row["product_id"] == product_id]
    before_by_id = {str(row["product_id"]): row for row in before_rows}
    after_by_id = {str(row["product_id"]): row for row in after_rows}
    ids = [key for key in after_by_id if key in before_by_id]
    if product_id and product_id not in after_by_id:
        return {
            "answerable": False,
            "missing": ["product"],
            "scenario": _scenario_dict(demand_pct, delay_days, lead_time_days),
            "as_of": today.isoformat(),
            "items": [],
        }
    if not product_id:
        ids = [
            key
            for key in ids
            if Decimal(str(before_by_id[key]["recommended_quantity"])) > 0
            or Decimal(str(after_by_id[key]["recommended_quantity"])) > 0
        ]
        if not ids:
            ids = list(after_by_id)
    items = [
        {
            "product_id": key,
            "sku": after_by_id[key]["sku"],
            "product_name": after_by_id[key]["product_name"],
            "before": _compare_side(before_by_id[key], today),
            "after": _compare_side(after_by_id[key], today),
        }
        for key in ids
    ]
    return {
        "answerable": True,
        "missing": [],
        "scenario": _scenario_dict(demand_pct, delay_days, lead_time_days),
        "as_of": today.isoformat(),
        "items": items,
    }


def _recommendation_rows(
    session: Session,
    *,
    business_id: str,
    demand_pct: Decimal | None = None,
    delay_days: int | None = None,
    lead_time_days: int | None = None,
) -> list[dict[str, object]]:
    on_hand_rows = session.execute(
        select(
            StockMovement.product_id,
            func.coalesce(func.sum(StockMovement.quantity), 0).label("on_hand"),
        )
        .where(StockMovement.business_id == business_id)
        .group_by(StockMovement.product_id)
    ).all()
    on_hand_by_product = {row.product_id: Decimal(row.on_hand) for row in on_hand_rows}
    forecasts = list_forecasts(session, business_id=business_id)
    forecast_by_product = {
        item["product_id"]: item for item in forecasts["items"] if isinstance(item, dict)
    }
    products = session.scalars(
        select(Product)
        .where(Product.business_id == business_id, Product.archived_at.is_(None))
        .order_by(Product.name.asc())
    ).all()
    suppliers_by_product = _supplier_options(session, business_id, [product.id for product in products])
    factor = _demand_factor(demand_pct)
    extra_delay = int(delay_days or 0)

    rows: list[dict[str, object]] = []
    for product in products:
        forecast = forecast_by_product.get(product.id, {})
        on_hand = on_hand_by_product.get(product.id, _ZERO)
        forecast_units = Decimal(str(forecast.get("forecast_units") or 0)) * factor
        daily_average = Decimal(str(forecast.get("daily_average") or 0)) * factor
        reorder_point = product.reorder_point or _ZERO
        safety_stock = product.safety_stock or _ZERO
        suppliers = [dict(item) for item in suppliers_by_product.get(product.id, [])]
        preferred = next((item for item in suppliers if item.get("is_preferred")), suppliers[0] if suppliers else None)
        original_lead = int(preferred["lead_time_days"]) if preferred is not None else 0
        effective_lead = original_lead if lead_time_days is None else int(lead_time_days)
        for option in suppliers:
            option["lead_time_days"] = effective_lead if lead_time_days is not None else option["lead_time_days"]
        extra_days = extra_delay + (effective_lead - original_lead)
        extra_units = daily_average * Decimal(extra_days)
        needed = max(reorder_point, forecast_units) + safety_stock + extra_units
        quantity = needed - on_hand
        if quantity < 0:
            quantity = _ZERO
        unit_cost = Decimal(str(preferred["unit_cost"])) if preferred is not None else None
        rows.append(
            {
                "product_id": product.id,
                "sku": product.sku,
                "product_name": product.name,
                "on_hand": on_hand,
                "reorder_point": product.reorder_point,
                "safety_stock": product.safety_stock,
                "forecast_units": forecast_units,
                "forecast_method": forecast.get("method"),
                "daily_average": daily_average,
                "horizon_days": forecasts["horizon_days"],
                "history_units": Decimal(str(forecast.get("history_units") or 0)),
                "recommended_quantity": quantity,
                "unit_cost": unit_cost,
                "lead_time_days": effective_lead,
                "original_lead_time_days": original_lead,
                "suppliers": suppliers,
            }
        )
    return rows


def _demand_factor(demand_pct: Decimal | None) -> Decimal:
    if demand_pct is None:
        return Decimal("1")
    return Decimal("1") + (Decimal(str(demand_pct)) / Decimal("100"))


def _scenario_dict(
    demand_pct: Decimal | None,
    delay_days: int | None,
    lead_time_days: int | None,
) -> dict[str, object]:
    return {
        "demand_pct": None if demand_pct is None else str(Decimal(str(demand_pct))),
        "delay_days": delay_days,
        "lead_time_days": lead_time_days,
    }


def _compare_side(row: dict[str, object], today: date) -> dict[str, object]:
    quantity = Decimal(str(row["recommended_quantity"]))
    unit_cost = row.get("unit_cost")
    cost = None if unit_cost is None else quantity * Decimal(str(unit_cost))
    daily = Decimal(str(row.get("daily_average") or 0))
    on_hand = Decimal(str(row["on_hand"]))
    return {
        "on_hand": on_hand,
        "forecast_units": Decimal(str(row["forecast_units"])),
        "daily_average": daily,
        "recommended_quantity": quantity,
        "unit_cost": unit_cost,
        "cost": cost,
        "lead_time_days": row.get("lead_time_days"),
        "stockout_date": _stockout_date(today, on_hand, daily),
        "forecast_method": row.get("forecast_method"),
    }


def _stockout_date(today: date, on_hand: Decimal, daily: Decimal) -> str | None:
    if daily <= 0:
        return None
    days = int((on_hand / daily).to_integral_value(rounding=ROUND_FLOOR))
    return (today + timedelta(days=max(0, days))).isoformat()


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
