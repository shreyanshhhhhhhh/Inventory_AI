from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import Product, StockMovement
from app.services.auth import signup
from app.services.catalog import create_product, create_supplier
from app.services.csv_import import import_products_csv, import_sales_csv
from app.services.inventory import record_movement


PRODUCT_CSV = """sku,name,category,location,quantity,unit,reorder_point,supplier,unit_cost,lead_time_days
IMP-001,Apples,Produce,Main location,12,each,5,Green Valley,1.25,2
IMP-002,Bananas,Produce,Main location,8,each,4,Green Valley,0.75,2
"""

INVALID_PRODUCT_CSV = """sku,name,category,location,quantity,unit,reorder_point,supplier,unit_cost,lead_time_days
,Missing SKU,Produce,Main location,1,each,1,Green Valley,1.00,1
IMP-003,Valid Item,Produce,Main location,2,each,1,Green Valley,1.00,1
"""


def _owner(db):
    return signup(
        db,
        full_name="Import Owner",
        email="import-owner@example.com",
        password="correct-horse-1",
        business_name="Import Shop",
    )


def test_valid_product_import(db) -> None:
    owner = _owner(db)
    result = import_products_csv(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        csv_text=PRODUCT_CSV,
    )
    assert result.success is True
    assert result.imported_count == 2
    assert db.scalar(select(func.count()).select_from(Product)) == 2


def test_product_import_row_errors(db) -> None:
    owner = _owner(db)
    result = import_products_csv(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        csv_text=INVALID_PRODUCT_CSV,
    )
    assert result.success is False
    assert result.imported_count == 0
    assert any(error.row == 2 for error in result.errors)
    assert db.scalar(select(func.count()).select_from(Product)) == 0


def test_product_import_skip_errors(db) -> None:
    owner = _owner(db)
    result = import_products_csv(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        csv_text=INVALID_PRODUCT_CSV,
        skip_errors=True,
    )
    assert result.imported_count == 1
    assert result.skipped_count == 1
    assert db.scalar(select(func.count()).select_from(Product)) == 1


def test_sales_import_creates_movements(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id
    from app.repositories import inventory as inventory_repo

    location_id = inventory_repo.list_locations(db, business_id)[0].id
    product = create_product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="SALE-001",
        name="Sale Item",
        category_id=None,
        unit="each",
        cost=Decimal("1.00"),
        price=Decimal("2.00"),
        reorder_point=Decimal("1"),
        safety_stock=Decimal("0"),
        preferred_supplier_id=None,
    )
    record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product.id,
        location_id=location_id,
        movement_type="receipt",
        quantity=Decimal("20"),
    )
    sales_csv = """date,sku,location,quantity,note
2026-01-10,SALE-001,Main location,3,Test sale
"""
    result = import_sales_csv(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        csv_text=sales_csv,
    )
    assert result.success is True
    assert result.imported_count == 1
    assert (
        db.scalar(
            select(func.count()).select_from(StockMovement).where(
                StockMovement.movement_type == "sale"
            )
        )
        == 1
    )


def test_sales_import_rejects_insufficient_stock(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id
    product = create_product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="SALE-002",
        name="Low Stock Item",
        category_id=None,
        unit="each",
        cost=Decimal("1.00"),
        price=Decimal("2.00"),
        reorder_point=Decimal("1"),
        safety_stock=Decimal("0"),
        preferred_supplier_id=None,
    )
    sales_csv = """date,sku,location,quantity,note
2026-01-10,SALE-002,Main location,5,Too much
"""
    result = import_sales_csv(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        csv_text=sales_csv,
    )
    assert result.success is False
    assert result.imported_count == 0
