import pytest
from sqlalchemy import func, select

from app.models import (
    Category,
    Location,
    Product,
    PurchaseOrder,
    StockMovement,
    Supplier,
)
from app.services.demo_seed import DemoSeedError, load_demo_data
from tests.helpers.tenant import signup_service_tenant


def _owner(db):
    return signup_service_tenant(
        db,
        full_name="Seed Owner",
        email="seed-owner@example.com",
        password="correct-horse-1",
        business_name="Seed Shop",
    )


def test_demo_seed_creates_expected_counts(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id
    result = load_demo_data(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
    )
    assert result["products_created"] == 100
    assert result["suppliers_created"] == 5
    assert result["categories_created"] == 8
    assert result["purchase_orders_created"] == 5
    assert result["sale_movements_created"] > 1000
    assert db.scalar(select(func.count()).select_from(Product)) == 100
    assert db.scalar(select(func.count()).select_from(Supplier)) == 5
    assert db.scalar(select(func.count()).select_from(Category)) == 8
    assert db.scalar(select(func.count()).select_from(PurchaseOrder)) == 5
    assert (
        db.scalar(
            select(func.count()).select_from(StockMovement).where(
                StockMovement.movement_type == "sale"
            )
        )
        == result["sale_movements_created"]
    )


def test_demo_seed_leaves_usable_stock_across_two_locations(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id
    load_demo_data(db, business_id=business_id, actor_user_id=owner.user.id)

    locations = db.scalars(select(Location).where(Location.business_id == business_id)).all()
    assert len(locations) == 2

    on_hand_by_product = dict(
        db.execute(
            select(StockMovement.product_id, func.sum(StockMovement.quantity))
            .where(StockMovement.business_id == business_id)
            .group_by(StockMovement.product_id)
        ).all()
    )
    in_stock = [qty for qty in on_hand_by_product.values() if qty > 0]
    assert len(in_stock) >= 90
    assert all(qty >= 0 for qty in on_hand_by_product.values())

    transfer_rows = db.scalars(
        select(StockMovement).where(StockMovement.movement_type == "transfer")
    ).all()
    assert transfer_rows
    assert {row.location_id for row in transfer_rows} == {loc.id for loc in locations}


def test_demo_seed_refuses_second_run(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id
    load_demo_data(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
    )
    with pytest.raises(DemoSeedError) as exc:
        load_demo_data(
            db,
            business_id=business_id,
            actor_user_id=owner.user.id,
        )
    assert exc.value.code == "demo_already_loaded"
