from datetime import date
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import PurchaseOrder, PurchaseOrderItem
from app.models.types import new_id, utcnow
from app.repositories import catalog as catalog_repo
from app.repositories import purchase_orders as po_repo
from app.repositories.purchase_orders import PurchaseOrderRow
from app.services.audit import log_action
from app.services.inventory import InventoryError, post_movement

PO_NUMBER_ATTEMPTS = 3


class PurchaseOrderError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, code: str = "bad_request") -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


def _decimal_dict(data: dict[str, object]) -> dict[str, object]:
    serialized: dict[str, object] = {}
    for key, value in data.items():
        if isinstance(value, Decimal):
            serialized[key] = str(value)
        elif isinstance(value, date):
            serialized[key] = value.isoformat()
        else:
            serialized[key] = value
    return serialized


def _po_payload(row: PurchaseOrderRow) -> dict[str, object]:
    return {
        "id": row.id,
        "po_number": row.po_number,
        "supplier_id": row.supplier_id,
        "supplier_name": row.supplier_name,
        "location_id": row.location_id,
        "status": row.status,
        "expected_on": row.expected_on.isoformat() if row.expected_on else None,
        "notes": row.notes,
        "line_items": [
            {
                "id": line.id,
                "product_id": line.product_id,
                "product_name": line.product_name,
                "quantity_ordered": str(line.quantity_ordered),
                "unit_cost": str(line.unit_cost),
            }
            for line in row.line_items
        ],
    }


def _compute_total(row: PurchaseOrderRow) -> Decimal:
    return sum(
        (line.quantity_ordered * line.unit_cost for line in row.line_items),
        start=Decimal("0"),
    )


def _row_to_dict(row: PurchaseOrderRow) -> dict[str, object]:
    total = _compute_total(row)
    return {
        "id": row.id,
        "po_number": row.po_number,
        "supplier_id": row.supplier_id,
        "supplier_name": row.supplier_name,
        "location_id": row.location_id,
        "status": row.status,
        "expected_date": row.expected_on,
        "notes": row.notes,
        "ordered_at": row.ordered_at,
        "total": total,
        "line_items": [
            {
                "id": line.id,
                "product_id": line.product_id,
                "product_name": line.product_name,
                "quantity": line.quantity_ordered,
                "unit_cost": line.unit_cost,
                "line_total": line.quantity_ordered * line.unit_cost,
            }
            for line in row.line_items
        ],
    }


def _resolve_unit_cost(
    session: Session,
    *,
    business_id: str,
    supplier_id: str,
    product_id: str,
    provided: Decimal | None,
) -> Decimal:
    if provided is not None:
        return provided
    link = catalog_repo.get_product_supplier_link(
        session,
        business_id,
        product_id,
        supplier_id,
    )
    if link is not None:
        return link.unit_cost
    product = catalog_repo.get_product(session, business_id, product_id)
    if product is None:
        raise PurchaseOrderError("Product not found.", status_code=404, code="not_found")
    if product.cost is not None:
        return product.cost
    raise PurchaseOrderError(
        "Unit cost is required because this product has no supplier cost or catalog cost.",
        code="bad_request",
    )


def _validate_supplier(session: Session, *, business_id: str, supplier_id: str) -> None:
    supplier = catalog_repo.get_supplier(session, business_id, supplier_id)
    if supplier is None:
        raise PurchaseOrderError("Supplier not found.", status_code=404, code="not_found")
    if supplier.archived_at is not None:
        raise PurchaseOrderError("Supplier is archived.", code="bad_request")


def _validate_location(session: Session, *, business_id: str, location_id: str) -> None:
    from app.repositories import inventory as inventory_repo

    location = inventory_repo.get_location(session, business_id, location_id)
    if location is None:
        raise PurchaseOrderError("Location not found.", status_code=404, code="not_found")


def _validate_line_items(
    session: Session,
    *,
    business_id: str,
    supplier_id: str,
    line_items: list[dict[str, object]],
) -> list[tuple[str, Decimal, Decimal]]:
    if not line_items:
        raise PurchaseOrderError("At least one line item is required.", code="bad_request")
    normalized: list[tuple[str, Decimal, Decimal]] = []
    for line in line_items:
        product_id = str(line["product_id"])
        quantity = Decimal(str(line["quantity"]))
        provided_cost = line.get("unit_cost")
        unit_cost = _resolve_unit_cost(
            session,
            business_id=business_id,
            supplier_id=supplier_id,
            product_id=product_id,
            provided=Decimal(str(provided_cost)) if provided_cost is not None else None,
        )
        product = catalog_repo.get_product(session, business_id, product_id)
        if product is None or product.archived_at is not None:
            raise PurchaseOrderError("Product not found.", status_code=404, code="not_found")
        if quantity <= 0:
            raise PurchaseOrderError("Line quantity must be greater than 0.", code="bad_request")
        normalized.append((product_id, quantity, unit_cost))
    return normalized


def create_po(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    supplier_id: str,
    expected_date: date | None,
    location_id: str | None,
    notes: str | None,
    line_items: list[dict[str, object]],
) -> dict[str, object]:
    for attempt in range(PO_NUMBER_ATTEMPTS):
        try:
            return _create_po_once(
                session,
                business_id=business_id,
                actor_user_id=actor_user_id,
                supplier_id=supplier_id,
                expected_date=expected_date,
                location_id=location_id,
                notes=notes,
                line_items=line_items,
            )
        except IntegrityError as exc:
            session.rollback()
            if "po_number" not in str(exc.orig) or attempt == PO_NUMBER_ATTEMPTS - 1:
                raise PurchaseOrderError(
                    "Could not save the purchase order. Try again.",
                    status_code=409,
                    code="conflict",
                ) from exc
    raise AssertionError("unreachable")


def _create_po_once(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    supplier_id: str,
    expected_date: date | None,
    location_id: str | None,
    notes: str | None,
    line_items: list[dict[str, object]],
) -> dict[str, object]:
    from app.repositories.businesses import get_business

    business = get_business(session, business_id)
    if business is None:
        raise PurchaseOrderError("Business not found.", status_code=404, code="not_found")

    _validate_supplier(session, business_id=business_id, supplier_id=supplier_id)
    resolved_location_id = location_id or po_repo.get_default_location_id(session, business_id)
    if resolved_location_id is None:
        raise PurchaseOrderError("No active location is available.", code="bad_request")
    _validate_location(session, business_id=business_id, location_id=resolved_location_id)

    normalized_lines = _validate_line_items(
        session,
        business_id=business_id,
        supplier_id=supplier_id,
        line_items=line_items,
    )

    order = PurchaseOrder(
        id=new_id(),
        business_id=business_id,
        supplier_id=supplier_id,
        location_id=resolved_location_id,
        status="draft",
        currency_code=business.currency_code,
        notes=notes,
        expected_on=expected_date,
        created_by_user_id=actor_user_id,
    )
    order.po_number = po_repo.next_po_number(session, business_id)
    session.add(order)
    session.flush()

    for product_id, quantity, unit_cost in normalized_lines:
        session.add(
            PurchaseOrderItem(
                id=new_id(),
                business_id=business_id,
                purchase_order_id=order.id,
                product_id=product_id,
                quantity_ordered=quantity,
                unit_cost=unit_cost,
            )
        )

    session.flush()
    row = po_repo.get_purchase_order_row(session, business_id, order.id)
    assert row is not None
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="purchase_order.create",
        entity_type="purchase_order",
        entity_id=order.id,
        before_data=None,
        after_data=_po_payload(row),
    )
    session.commit()
    return _row_to_dict(row)


def update_po(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    purchase_order_id: str,
    supplier_id: str | None = None,
    expected_date: date | None = None,
    location_id: str | None = None,
    notes: str | None = None,
    line_items: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    order = po_repo.get_purchase_order(session, business_id, purchase_order_id)
    if order is None:
        raise PurchaseOrderError("Purchase order not found.", status_code=404, code="not_found")
    if order.status != "draft":
        raise PurchaseOrderError("Only draft purchase orders can be edited.", code="bad_request")

    before_row = po_repo.get_purchase_order_row(session, business_id, purchase_order_id)
    assert before_row is not None

    next_supplier_id = supplier_id or order.supplier_id
    _validate_supplier(session, business_id=business_id, supplier_id=next_supplier_id)

    if location_id is not None:
        _validate_location(session, business_id=business_id, location_id=location_id)
        order.location_id = location_id

    if supplier_id is not None:
        order.supplier_id = supplier_id
    if expected_date is not None:
        order.expected_on = expected_date
    if notes is not None:
        order.notes = notes

    if line_items is not None:
        normalized_lines = _validate_line_items(
            session,
            business_id=business_id,
            supplier_id=next_supplier_id,
            line_items=line_items,
        )
        existing_items = po_repo.list_purchase_order_items(session, business_id, order.id)
        for item in existing_items:
            session.delete(item)
        session.flush()
        for product_id, quantity, unit_cost in normalized_lines:
            session.add(
                PurchaseOrderItem(
                    id=new_id(),
                    business_id=business_id,
                    purchase_order_id=order.id,
                    product_id=product_id,
                    quantity_ordered=quantity,
                    unit_cost=unit_cost,
                )
            )

    session.flush()
    after_row = po_repo.get_purchase_order_row(session, business_id, purchase_order_id)
    assert after_row is not None
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="purchase_order.update",
        entity_type="purchase_order",
        entity_id=order.id,
        before_data=_po_payload(before_row),
        after_data=_po_payload(after_row),
    )
    session.commit()
    return _row_to_dict(after_row)


def get_po(
    session: Session,
    *,
    business_id: str,
    purchase_order_id: str,
) -> dict[str, object]:
    row = po_repo.get_purchase_order_row(session, business_id, purchase_order_id)
    if row is None:
        raise PurchaseOrderError("Purchase order not found.", status_code=404, code="not_found")
    return _row_to_dict(row)


def list_pos(
    session: Session,
    *,
    business_id: str,
    status: str | None = None,
    supplier_id: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[dict[str, object]], int]:
    rows, total = po_repo.list_purchase_orders(
        session,
        business_id=business_id,
        status=status,
        supplier_id=supplier_id,
        page=page,
        page_size=page_size,
    )
    return [_row_to_dict(row) for row in rows], total


def transition_po(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    purchase_order_id: str,
    action: str,
    actor_role: str,
) -> dict[str, object]:
    order = po_repo.get_purchase_order(session, business_id, purchase_order_id, lock=True)
    if order is None:
        raise PurchaseOrderError("Purchase order not found.", status_code=404, code="not_found")

    before_row = po_repo.get_purchase_order_row(session, business_id, purchase_order_id)
    assert before_row is not None
    current_status = order.status

    if action == "approve":
        if actor_role != "owner":
            raise PurchaseOrderError(
                "Only owners can approve purchase orders.",
                status_code=403,
                code="forbidden",
            )
        if current_status != "draft":
            raise PurchaseOrderError(
                "Only draft purchase orders can be approved.",
                status_code=409,
                code="invalid_transition",
            )
        order.status = "approved"
    elif action == "send":
        if current_status != "approved":
            raise PurchaseOrderError(
                "Only approved purchase orders can be marked sent.",
                status_code=409,
                code="invalid_transition",
            )
        order.status = "sent"
        order.ordered_at = utcnow()
    elif action == "receive":
        if current_status != "sent":
            raise PurchaseOrderError(
                "Only sent purchase orders can be received.",
                status_code=409,
                code="invalid_transition",
            )
        line_items = po_repo.list_purchase_order_items(session, business_id, order.id)
        if not line_items:
            raise PurchaseOrderError("Purchase order has no line items.", code="bad_request")
        try:
            for item in line_items:
                post_movement(
                    session,
                    business_id=business_id,
                    actor_user_id=actor_user_id,
                    product_id=item.product_id,
                    location_id=order.location_id,
                    movement_type="purchase_receipt",
                    quantity=item.quantity_ordered,
                    note=f"Received {order.po_number}",
                    purchase_order_item_id=item.id,
                    commit=False,
                )
            order.status = "received"
            session.flush()
            after_row = po_repo.get_purchase_order_row(session, business_id, purchase_order_id)
            assert after_row is not None
            log_action(
                session,
                business_id=business_id,
                actor_user_id=actor_user_id,
                action="purchase_order.receive",
                entity_type="purchase_order",
                entity_id=order.id,
                before_data=_po_payload(before_row),
                after_data=_po_payload(after_row),
            )
            session.commit()
            return _row_to_dict(after_row)
        except InventoryError as exc:
            session.rollback()
            raise PurchaseOrderError(
                exc.message,
                status_code=exc.status_code,
                code=exc.code,
            ) from exc
    elif action == "cancel":
        if current_status in {"received", "cancelled"}:
            raise PurchaseOrderError(
                "This purchase order cannot be cancelled.",
                status_code=409,
                code="invalid_transition",
            )
        order.status = "cancelled"
    else:
        raise PurchaseOrderError("Unsupported transition action.", code="bad_request")

    session.flush()
    after_row = po_repo.get_purchase_order_row(session, business_id, purchase_order_id)
    assert after_row is not None
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action=f"purchase_order.{action}",
        entity_type="purchase_order",
        entity_id=order.id,
        before_data=_po_payload(before_row),
        after_data=_po_payload(after_row),
    )
    session.commit()
    return _row_to_dict(after_row)
