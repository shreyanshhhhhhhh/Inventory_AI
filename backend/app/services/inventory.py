from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import PurchaseOrderItem, StockMovement, User
from app.models.types import new_id, utcnow
from app.repositories import inventory as inventory_repo
from app.repositories.inventory import MovementHistoryRow, StockLevelRow
from app.services.audit import log_action


class InventoryError(Exception):
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
        elif isinstance(value, datetime):
            serialized[key] = value.isoformat()
        else:
            serialized[key] = value
    return serialized


def _movement_payload(movement: StockMovement) -> dict[str, object]:
    return _decimal_dict(
        {
            "id": movement.id,
            "business_id": movement.business_id,
            "product_id": movement.product_id,
            "location_id": movement.location_id,
            "movement_type": movement.movement_type,
            "quantity": movement.quantity,
            "reason": movement.reason,
            "note": movement.note,
            "transfer_group_id": movement.transfer_group_id,
            "sale_group_id": movement.sale_group_id,
            "purchase_order_item_id": movement.purchase_order_item_id,
            "occurred_at": movement.occurred_at,
            "created_by_user_id": movement.created_by_user_id,
        }
    )


def compute_stock_status(on_hand: Decimal, reorder_point: Decimal | None) -> str:
    if on_hand <= 0:
        return "out"
    if reorder_point is not None and on_hand <= reorder_point:
        return "low"
    return "in_stock"


def _derive_signed_quantity(movement_type: str, quantity: Decimal) -> Decimal:
    if movement_type in {"receipt", "purchase_receipt"}:
        return abs(quantity)
    if movement_type == "sale":
        return -abs(quantity)
    if movement_type == "adjustment":
        return quantity
    if movement_type == "transfer":
        return -abs(quantity)
    raise InventoryError("Unsupported movement type.", code="bad_request")


def _ensure_not_future(occurred_at: datetime) -> datetime:
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    else:
        occurred_at = occurred_at.astimezone(timezone.utc)
    if occurred_at > utcnow():
        raise InventoryError("Movement time cannot be in the future.", code="bad_request")
    return occurred_at


def _ensure_stock_available(
    session: Session,
    *,
    business_id: str,
    product_id: str,
    location_id: str,
    signed_quantity: Decimal,
) -> None:
    if signed_quantity >= 0:
        return
    on_hand = inventory_repo.get_on_hand(
        session,
        business_id=business_id,
        product_id=product_id,
        location_id=location_id,
    )
    if on_hand + signed_quantity < 0:
        raise InventoryError(
            "This movement would make stock negative.",
            status_code=409,
            code="insufficient_stock",
        )


def list_locations(session: Session, *, business_id: str) -> list[dict[str, object]]:
    return [
        {
            "id": location.id,
            "name": location.name,
            "is_default": location.is_default,
        }
        for location in inventory_repo.list_locations(session, business_id)
    ]


def get_stock_levels(
    session: Session,
    *,
    business_id: str,
    search: str | None = None,
    location_id: str | None = None,
    low_only: bool = False,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[dict[str, object]], int]:
    rows, total = inventory_repo.list_stock_levels(
        session,
        business_id=business_id,
        search=search,
        location_id=location_id,
        low_only=low_only,
        page=page,
        page_size=page_size,
    )
    items = [_stock_level_dict(row) for row in rows]
    return items, total


def _stock_level_dict(row: StockLevelRow) -> dict[str, object]:
    return {
        "product_id": row.product_id,
        "location_id": row.location_id,
        "sku": row.sku,
        "product_name": row.product_name,
        "location_name": row.location_name,
        "on_hand": row.on_hand,
        "reorder_point": row.reorder_point,
        "status": compute_stock_status(row.on_hand, row.reorder_point),
    }


def get_movement_history(
    session: Session,
    *,
    business_id: str,
    movement_type: str | None = None,
    product_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[dict[str, object]], int]:
    rows, total = inventory_repo.list_movements(
        session,
        business_id=business_id,
        movement_type=movement_type,
        product_id=product_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return [_movement_dict(row) for row in rows], total


def _movement_dict(row: MovementHistoryRow) -> dict[str, object]:
    return {
        "id": row.id,
        "occurred_at": row.occurred_at,
        "product_id": row.product_id,
        "product_name": row.product_name,
        "location_id": row.location_id,
        "location_name": row.location_name,
        "movement_type": row.movement_type,
        "quantity": row.quantity,
        "note": row.note,
        "reason": row.reason,
        "user_id": row.created_by_user_id,
        "user_name": row.user_name,
    }


def post_movement(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    product_id: str,
    location_id: str,
    movement_type: str,
    quantity: Decimal,
    note: str | None = None,
    purchase_order_item_id: str | None = None,
    destination_location_id: str | None = None,
    occurred_at: datetime | None = None,
    sale_group_id: str | None = None,
    commit: bool = True,
) -> StockMovement:
    product = inventory_repo.get_product(session, business_id, product_id)
    if product is None:
        raise InventoryError("Product not found.", status_code=404, code="not_found")

    source_location = inventory_repo.get_location(session, business_id, location_id)
    if source_location is None:
        raise InventoryError("Location not found.", status_code=404, code="not_found")

    when = _ensure_not_future(occurred_at or utcnow())

    if movement_type == "transfer":
        if destination_location_id is None:
            raise InventoryError("Transfers require a destination location.", code="bad_request")
        destination = inventory_repo.get_location(session, business_id, destination_location_id)
        if destination is None:
            raise InventoryError("Destination location not found.", status_code=404, code="not_found")
        if destination_location_id == location_id:
            raise InventoryError("Transfer source and destination must differ.", code="bad_request")
        movement = _post_transfer(
            session,
            business_id=business_id,
            actor_user_id=actor_user_id,
            product_id=product_id,
            source_location_id=location_id,
            destination_location_id=destination_location_id,
            quantity=quantity,
            note=note,
            occurred_at=when,
            commit=commit,
        )
        return movement

    if movement_type == "purchase_receipt":
        if purchase_order_item_id is None:
            raise InventoryError(
                "Purchase receipts must reference a purchase order line.",
                code="bad_request",
            )

    signed_quantity = _derive_signed_quantity(movement_type, quantity)

    if movement_type == "adjustment" and not note:
        raise InventoryError("Adjustments require a note.", code="bad_request")

    inventory_repo.lock_product_for_posting(session, business_id=business_id, product_id=product_id)

    if movement_type == "purchase_receipt" and purchase_order_item_id is not None:
        po_item = session.get(PurchaseOrderItem, purchase_order_item_id)
        if po_item is None or po_item.business_id != business_id:
            raise InventoryError("Purchase order line not found.", status_code=404, code="not_found")
        received = inventory_repo.get_received_quantity(
            session,
            business_id=business_id,
            purchase_order_item_id=purchase_order_item_id,
        )
        if received + signed_quantity > po_item.quantity_ordered:
            raise InventoryError(
                "Received quantity would exceed the quantity ordered on this line.",
                status_code=409,
                code="over_receipt",
            )

    _ensure_stock_available(
        session,
        business_id=business_id,
        product_id=product_id,
        location_id=location_id,
        signed_quantity=signed_quantity,
    )

    movement = StockMovement(
        id=new_id(),
        business_id=business_id,
        product_id=product_id,
        location_id=location_id,
        movement_type=movement_type,
        quantity=signed_quantity,
        reason=note if movement_type == "adjustment" else None,
        note=note if movement_type not in {"adjustment", "purchase_receipt"} else note,
        sale_group_id=(sale_group_id or new_id()) if movement_type == "sale" else None,
        purchase_order_item_id=purchase_order_item_id,
        occurred_at=when,
        created_by_user_id=actor_user_id,
    )
    inventory_repo.insert_movement(session, movement)
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="stock.movement.post",
        entity_type="stock_movement",
        entity_id=movement.id,
        before_data=None,
        after_data=_movement_payload(movement),
    )
    if commit:
        session.commit()
        session.refresh(movement)
    return movement


def record_movement(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    product_id: str,
    location_id: str,
    movement_type: str,
    quantity: Decimal,
    note: str | None = None,
    destination_location_id: str | None = None,
    occurred_at: datetime | None = None,
) -> dict[str, object]:
    movement = post_movement(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        product_id=product_id,
        location_id=location_id,
        movement_type=movement_type,
        quantity=quantity,
        note=note,
        destination_location_id=destination_location_id,
        occurred_at=occurred_at,
        commit=True,
    )
    product = inventory_repo.get_product(session, business_id, product_id)
    source_location = inventory_repo.get_location(session, business_id, location_id)
    actor = session.get(User, actor_user_id)
    assert product is not None and source_location is not None
    return _movement_dict(
        MovementHistoryRow(
            id=movement.id,
            occurred_at=movement.occurred_at,
            product_id=product.id,
            product_name=product.name,
            location_id=source_location.id,
            location_name=source_location.name,
            movement_type=movement.movement_type,
            quantity=movement.quantity,
            note=movement.note,
            reason=movement.reason,
            created_by_user_id=actor_user_id,
            user_name=actor.full_name if actor else "",
        )
    )


def record_sale(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    location_id: str,
    lines: list[tuple[str, Decimal]],
    note: str | None = None,
    occurred_at: datetime | None = None,
) -> dict[str, object]:
    """Post one sale movement per line, all sharing a sale_group_id, in one transaction."""
    if not lines:
        raise InventoryError("A sale needs at least one line.", code="bad_request")
    product_ids = [product_id for product_id, _ in lines]
    if len(set(product_ids)) != len(product_ids):
        raise InventoryError("Each product can appear only once in a sale.", code="bad_request")

    group_id = new_id()
    movement_ids: list[str] = []
    try:
        for product_id, quantity in lines:
            if quantity <= 0:
                raise InventoryError("Sale quantities must be greater than 0.", code="bad_request")
            movement = post_movement(
                session,
                business_id=business_id,
                actor_user_id=actor_user_id,
                product_id=product_id,
                location_id=location_id,
                movement_type="sale",
                quantity=quantity,
                note=note,
                occurred_at=occurred_at,
                sale_group_id=group_id,
                commit=False,
            )
            movement_ids.append(movement.id)
    except InventoryError:
        session.rollback()
        raise
    session.commit()

    rows, _ = inventory_repo.list_movements(
        session,
        business_id=business_id,
        movement_type="sale",
        product_id=None,
        date_from=None,
        date_to=None,
        page=1,
        page_size=100,
        sale_group_id=group_id,
    )
    return {"sale_group_id": group_id, "items": [_movement_dict(row) for row in rows]}


def _post_transfer(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    product_id: str,
    source_location_id: str,
    destination_location_id: str,
    quantity: Decimal,
    note: str | None,
    occurred_at: datetime,
    commit: bool,
) -> StockMovement:
    transfer_quantity = abs(quantity)
    out_quantity = -transfer_quantity

    inventory_repo.lock_product_for_posting(session, business_id=business_id, product_id=product_id)
    _ensure_stock_available(
        session,
        business_id=business_id,
        product_id=product_id,
        location_id=source_location_id,
        signed_quantity=out_quantity,
    )

    group_id = new_id()
    out_row = StockMovement(
        id=new_id(),
        business_id=business_id,
        product_id=product_id,
        location_id=source_location_id,
        movement_type="transfer",
        quantity=out_quantity,
        note=note,
        transfer_group_id=group_id,
        occurred_at=occurred_at,
        created_by_user_id=actor_user_id,
    )
    in_row = StockMovement(
        id=new_id(),
        business_id=business_id,
        product_id=product_id,
        location_id=destination_location_id,
        movement_type="transfer",
        quantity=transfer_quantity,
        note=note,
        transfer_group_id=group_id,
        occurred_at=occurred_at,
        created_by_user_id=actor_user_id,
    )
    inventory_repo.insert_movement(session, out_row)
    inventory_repo.insert_movement(session, in_row)
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="stock.movement.post",
        entity_type="stock_movement",
        entity_id=group_id,
        before_data=None,
        after_data={
            "transfer_group_id": group_id,
            "out_movement_id": out_row.id,
            "in_movement_id": in_row.id,
            "quantity": str(transfer_quantity),
        },
    )
    if commit:
        session.commit()
        session.refresh(out_row)
    return out_row
