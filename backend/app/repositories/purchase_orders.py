from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Product, PurchaseOrder, PurchaseOrderItem, Supplier


@dataclass(frozen=True)
class PurchaseOrderLineRow:
    id: str
    product_id: str
    product_name: str
    quantity_ordered: Decimal
    unit_cost: Decimal


@dataclass(frozen=True)
class PurchaseOrderRow:
    id: str
    po_number: str
    supplier_id: str
    supplier_name: str
    location_id: str
    status: str
    expected_on: date | None
    notes: str | None
    ordered_at: object | None
    created_by_user_id: str
    line_items: list[PurchaseOrderLineRow]


def get_default_location_id(session: Session, business_id: str) -> str | None:
    from app.models import Location

    location = session.scalar(
        select(Location.id).where(
            Location.business_id == business_id,
            Location.archived_at.is_(None),
            Location.is_default.is_(True),
        )
    )
    if location is not None:
        return location
    location = session.scalar(
        select(Location.id).where(
            Location.business_id == business_id,
            Location.archived_at.is_(None),
        )
    )
    return location


def next_po_number(session: Session, business_id: str) -> str:
    numbers = session.scalars(
        select(PurchaseOrder.po_number).where(PurchaseOrder.business_id == business_id)
    )
    highest = 0
    for po_number in numbers:
        if not po_number.startswith("PO-"):
            continue
        suffix = po_number.removeprefix("PO-")
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"PO-{highest + 1:04d}"


def get_purchase_order(
    session: Session,
    business_id: str,
    purchase_order_id: str,
) -> PurchaseOrder | None:
    return session.scalar(
        select(PurchaseOrder).where(
            PurchaseOrder.business_id == business_id,
            PurchaseOrder.id == purchase_order_id,
        )
    )


def list_purchase_order_items(
    session: Session,
    business_id: str,
    purchase_order_id: str,
) -> list[PurchaseOrderItem]:
    return list(
        session.scalars(
            select(PurchaseOrderItem).where(
                PurchaseOrderItem.business_id == business_id,
                PurchaseOrderItem.purchase_order_id == purchase_order_id,
            )
        )
    )


def list_purchase_orders(
    session: Session,
    *,
    business_id: str,
    status: str | None,
    supplier_id: str | None,
    page: int,
    page_size: int,
) -> tuple[list[PurchaseOrderRow], int]:
    stmt = (
        select(PurchaseOrder, Supplier.name)
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .where(PurchaseOrder.business_id == business_id)
    )
    if status:
        stmt = stmt.where(PurchaseOrder.status == status)
    if supplier_id:
        stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int(session.scalar(count_stmt) or 0)

    rows = session.execute(
        stmt.order_by(PurchaseOrder.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items: list[PurchaseOrderRow] = []
    for order, supplier_name in rows:
        line_rows = session.execute(
            select(
                PurchaseOrderItem.id,
                PurchaseOrderItem.product_id,
                Product.name,
                PurchaseOrderItem.quantity_ordered,
                PurchaseOrderItem.unit_cost,
            )
            .join(Product, Product.id == PurchaseOrderItem.product_id)
            .where(
                PurchaseOrderItem.business_id == business_id,
                PurchaseOrderItem.purchase_order_id == order.id,
            )
            .order_by(Product.name.asc())
        ).all()
        items.append(
            PurchaseOrderRow(
                id=order.id,
                po_number=order.po_number,
                supplier_id=order.supplier_id,
                supplier_name=supplier_name,
                location_id=order.location_id,
                status=order.status,
                expected_on=order.expected_on,
                notes=order.notes,
                ordered_at=order.ordered_at,
                created_by_user_id=order.created_by_user_id,
                line_items=[
                    PurchaseOrderLineRow(
                        id=line[0],
                        product_id=line[1],
                        product_name=line[2],
                        quantity_ordered=Decimal(line[3]),
                        unit_cost=Decimal(line[4]),
                    )
                    for line in line_rows
                ],
            )
        )
    return items, total


def get_purchase_order_row(
    session: Session,
    business_id: str,
    purchase_order_id: str,
) -> PurchaseOrderRow | None:
    order = session.execute(
        select(PurchaseOrder, Supplier.name)
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .where(
            PurchaseOrder.business_id == business_id,
            PurchaseOrder.id == purchase_order_id,
        )
    ).first()
    if order is None:
        return None
    po, supplier_name = order
    line_rows = session.execute(
        select(
            PurchaseOrderItem.id,
            PurchaseOrderItem.product_id,
            Product.name,
            PurchaseOrderItem.quantity_ordered,
            PurchaseOrderItem.unit_cost,
        )
        .join(Product, Product.id == PurchaseOrderItem.product_id)
        .where(
            PurchaseOrderItem.business_id == business_id,
            PurchaseOrderItem.purchase_order_id == po.id,
        )
        .order_by(Product.name.asc())
    ).all()
    return PurchaseOrderRow(
        id=po.id,
        po_number=po.po_number,
        supplier_id=po.supplier_id,
        supplier_name=supplier_name,
        location_id=po.location_id,
        status=po.status,
        expected_on=po.expected_on,
        notes=po.notes,
        ordered_at=po.ordered_at,
        created_by_user_id=po.created_by_user_id,
        line_items=[
            PurchaseOrderLineRow(
                id=line[0],
                product_id=line[1],
                product_name=line[2],
                quantity_ordered=Decimal(line[3]),
                unit_cost=Decimal(line[4]),
            )
            for line in line_rows
        ],
    )
