from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import AuditLog, Location, StockMovement
from app.models.types import new_id
from app.services.auth import signup
from app.services.catalog import create_product
from app.services.inventory import (
    InventoryError,
    compute_stock_status,
    get_movement_history,
    get_stock_levels,
    record_movement,
)


def _owner(db):
    return signup(
        db,
        full_name="Ada Owner",
        email="inventory-owner@example.com",
        password="correct-horse-1",
        business_name="Inventory Shop",
    )


def _other_owner(db):
    return signup(
        db,
        full_name="Bea Owner",
        email="inventory-other@example.com",
        password="correct-horse-1",
        business_name="Other Inventory Shop",
    )


def _default_location_id(db, business_id: str) -> str:
    location = db.scalar(
        select(Location).where(
            Location.business_id == business_id,
            Location.is_default.is_(True),
        )
    )
    assert location is not None
    return location.id


def _product(
    db,
    *,
    business_id: str,
    actor_user_id: str,
    sku: str = "SKU-1",
    reorder_point: str = "10",
) -> str:
    product = create_product(
        db,
        business_id=business_id,
        actor_user_id=actor_user_id,
        sku=sku,
        name=f"Product {sku}",
        category_id=None,
        unit="each",
        cost=Decimal("1.00"),
        price=Decimal("2.00"),
        reorder_point=Decimal(reorder_point),
        safety_stock=Decimal("0"),
        preferred_supplier_id=None,
    )
    return product.id


def test_derived_stock_after_movement_sequence(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id
    location_id = _default_location_id(db, business_id)
    product_id = _product(db, business_id=business_id, actor_user_id=owner.user.id)

    record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_id,
        location_id=location_id,
        movement_type="receipt",
        quantity=Decimal("20"),
        note="Initial stock",
    )
    record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_id,
        location_id=location_id,
        movement_type="sale",
        quantity=Decimal("5"),
    )

    items, total = get_stock_levels(
        db,
        business_id=business_id,
        page=1,
        page_size=10,
    )
    assert total == 1
    assert items[0]["on_hand"] == Decimal("15")
    assert items[0]["status"] == "in_stock"


def test_sale_rejects_negative_stock(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id
    location_id = _default_location_id(db, business_id)
    product_id = _product(db, business_id=business_id, actor_user_id=owner.user.id)

    record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_id,
        location_id=location_id,
        movement_type="receipt",
        quantity=Decimal("3"),
    )

    with pytest.raises(InventoryError) as exc:
        record_movement(
            db,
            business_id=business_id,
            actor_user_id=owner.user.id,
            product_id=product_id,
            location_id=location_id,
            movement_type="sale",
            quantity=Decimal("5"),
        )
    assert exc.value.code == "insufficient_stock"
    assert db.scalar(select(func.count()).select_from(StockMovement)) == 1


def test_adjustment_with_note_can_go_negative(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id
    location_id = _default_location_id(db, business_id)
    product_id = _product(db, business_id=business_id, actor_user_id=owner.user.id)

    record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_id,
        location_id=location_id,
        movement_type="receipt",
        quantity=Decimal("2"),
    )
    record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_id,
        location_id=location_id,
        movement_type="adjustment",
        quantity=Decimal("-5"),
        note="Damaged during unload",
    )

    items, _ = get_stock_levels(db, business_id=business_id, page=1, page_size=10)
    assert items[0]["on_hand"] == Decimal("-3")


def test_adjustment_without_note_fails(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id
    location_id = _default_location_id(db, business_id)
    product_id = _product(db, business_id=business_id, actor_user_id=owner.user.id)

    with pytest.raises(InventoryError) as exc:
        record_movement(
            db,
            business_id=business_id,
            actor_user_id=owner.user.id,
            product_id=product_id,
            location_id=location_id,
            movement_type="adjustment",
            quantity=Decimal("-1"),
            note=None,
        )
    assert "note" in exc.value.message.lower()


def test_sign_rules_per_type(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id
    location_id = _default_location_id(db, business_id)
    product_id = _product(db, business_id=business_id, actor_user_id=owner.user.id)

    receipt = record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_id,
        location_id=location_id,
        movement_type="receipt",
        quantity=Decimal("4"),
    )
    assert receipt["quantity"] == Decimal("4")

    sale = record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_id,
        location_id=location_id,
        movement_type="sale",
        quantity=Decimal("2"),
    )
    assert sale["quantity"] == Decimal("-2")


def test_status_thresholds(db) -> None:
    assert compute_stock_status(Decimal("0"), Decimal("10")) == "out"
    assert compute_stock_status(Decimal("5"), Decimal("10")) == "low"
    assert compute_stock_status(Decimal("11"), Decimal("10")) == "in_stock"
    assert compute_stock_status(Decimal("3"), None) == "in_stock"


def test_low_only_stock_filter(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id
    location_id = _default_location_id(db, business_id)
    low_product = _product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="LOW-1",
        reorder_point="10",
    )
    ok_product = _product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="OK-1",
        reorder_point="10",
    )

    record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=low_product,
        location_id=location_id,
        movement_type="receipt",
        quantity=Decimal("5"),
    )
    record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=ok_product,
        location_id=location_id,
        movement_type="receipt",
        quantity=Decimal("20"),
    )

    items, total = get_stock_levels(
        db,
        business_id=business_id,
        low_only=True,
        page=1,
        page_size=10,
    )
    assert total == 1
    assert items[0]["product_id"] == low_product
    assert items[0]["status"] == "low"


def test_transfer_inserts_pair_and_balances(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id
    source_id = _default_location_id(db, business_id)
    destination = Location(
        id=new_id(),
        business_id=business_id,
        name="Back stockroom",
        is_default=False,
    )
    db.add(destination)
    db.commit()
    product_id = _product(db, business_id=business_id, actor_user_id=owner.user.id)

    record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_id,
        location_id=source_id,
        movement_type="receipt",
        quantity=Decimal("10"),
    )
    record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_id,
        location_id=source_id,
        movement_type="transfer",
        quantity=Decimal("4"),
        destination_location_id=destination.id,
    )

    transfer_rows = list(
        db.scalars(
            select(StockMovement).where(
                StockMovement.business_id == business_id,
                StockMovement.movement_type == "transfer",
            )
        )
    )
    assert len(transfer_rows) == 2
    assert sum(row.quantity for row in transfer_rows) == 0


def test_movement_writes_audit_log(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id
    location_id = _default_location_id(db, business_id)
    product_id = _product(db, business_id=business_id, actor_user_id=owner.user.id)

    record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_id,
        location_id=location_id,
        movement_type="receipt",
        quantity=Decimal("1"),
    )

    assert (
        db.scalar(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.action == "stock.movement.post"
            )
        )
        == 1
    )


def test_tenant_isolation_for_movements(db) -> None:
    owner = _owner(db)
    other = _other_owner(db)
    location_id = _default_location_id(db, owner.user.business_id)
    product_id = _product(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
    )

    record_movement(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        product_id=product_id,
        location_id=location_id,
        movement_type="receipt",
        quantity=Decimal("7"),
    )

    items, total = get_stock_levels(
        db,
        business_id=other.user.business_id,
        page=1,
        page_size=10,
    )
    assert total == 0
    assert items == []

    history, history_total = get_movement_history(
        db,
        business_id=other.user.business_id,
        page=1,
        page_size=10,
    )
    assert history_total == 0
    assert history == []


def test_concurrent_safe_second_sale_rejected(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id
    location_id = _default_location_id(db, business_id)
    product_id = _product(db, business_id=business_id, actor_user_id=owner.user.id)

    record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_id,
        location_id=location_id,
        movement_type="receipt",
        quantity=Decimal("5"),
    )
    record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_id,
        location_id=location_id,
        movement_type="sale",
        quantity=Decimal("3"),
    )

    with pytest.raises(InventoryError):
        record_movement(
            db,
            business_id=business_id,
            actor_user_id=owner.user.id,
            product_id=product_id,
            location_id=location_id,
            movement_type="sale",
            quantity=Decimal("3"),
        )

    items, _ = get_stock_levels(db, business_id=business_id, page=1, page_size=10)
    assert items[0]["on_hand"] == Decimal("2")
