from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PurchaseOrder, Supplier
from app.models.types import utcnow

_OPEN_STATUSES = ("draft", "approved", "sent")
_OVERDUE_STATUSES = ("approved", "sent")


def get_supplier_reliability(
    session: Session,
    *,
    business_id: str,
    supplier_id: str | None = None,
) -> list[dict[str, object]]:
    today = utcnow().date()
    suppliers = session.scalars(
        select(Supplier)
        .where(
            Supplier.business_id == business_id,
            Supplier.archived_at.is_(None),
            *( [Supplier.id == supplier_id] if supplier_id else [] ),
        )
        .order_by(Supplier.name.asc())
    ).all()
    orders = session.scalars(
        select(PurchaseOrder).where(PurchaseOrder.business_id == business_id)
    ).all()
    by_supplier: dict[str, list[PurchaseOrder]] = {}
    for order in orders:
        by_supplier.setdefault(order.supplier_id, []).append(order)

    rows: list[dict[str, object]] = []
    for supplier in suppliers:
        supplier_orders = by_supplier.get(supplier.id, [])
        open_count = sum(1 for order in supplier_orders if order.status in _OPEN_STATUSES)
        overdue_count = sum(
            1
            for order in supplier_orders
            if order.status in _OVERDUE_STATUSES
            and _is_overdue(order.expected_on, today)
        )
        received_count = sum(1 for order in supplier_orders if order.status == "received")
        po_count = len(supplier_orders)
        if po_count == 0:
            score = 1.0
        else:
            score = max(0.0, 1.0 - (overdue_count / po_count))
        rows.append(
            {
                "supplier_id": supplier.id,
                "supplier_name": supplier.name,
                "lead_time_days": supplier.lead_time_days,
                "purchase_order_count": po_count,
                "open_count": open_count,
                "overdue_count": overdue_count,
                "received_count": received_count,
                "reliability_score": score,
            }
        )
    return rows


def _is_overdue(expected_on: date | None, today: date) -> bool:
    return expected_on is not None and expected_on < today
