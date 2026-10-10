import pytest
from sqlalchemy import func, select

from app.models import Category, Product, PurchaseOrder, StockMovement, Supplier
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
