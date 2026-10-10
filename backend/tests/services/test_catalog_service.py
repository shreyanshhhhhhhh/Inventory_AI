from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import AuditLog, Category, Product, Supplier
from app.repositories.catalog import get_product_row
from app.services.catalog import (
    CatalogError,
    archive_product,
    archive_supplier,
    list_suppliers,
    restore_product,
    restore_supplier,
    create_category,
    create_product,
    create_supplier,
    list_products,
    update_product,
)
from tests.helpers.tenant import signup_service_tenant


def _owner(db):
    return signup_service_tenant(
        db,
        full_name="Ada Owner",
        email="catalog-owner@example.com",
        password="correct-horse-1",
        business_name="Catalog Shop",
    )


def _other_owner(db):
    return signup_service_tenant(
        db,
        full_name="Bea Owner",
        email="catalog-other@example.com",
        password="correct-horse-1",
        business_name="Other Shop",
    )


def test_category_crud_writes_audit_rows(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id

    category = create_category(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        name="Produce",
    )
    assert category.name == "Produce"
    assert db.scalar(select(func.count()).select_from(Category)) == 1
    assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "category.create")) == 1


def test_supplier_crud(db) -> None:
    owner = _owner(db)
    supplier = create_supplier(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        name="Green Valley",
        email="orders@greenvalley.example",
        phone="555-0100",
        lead_time_days=2,
    )
    assert supplier.lead_time_days == 2
    assert db.scalar(select(func.count()).select_from(Supplier)) == 1


def test_product_sku_must_be_unique_per_business(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id
    create_product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="SKU-1",
        name="Apples",
        category_id=None,
        unit="each",
        cost=Decimal("1.25"),
        price=Decimal("2.49"),
        reorder_point=Decimal("10"),
        safety_stock=Decimal("5"),
        preferred_supplier_id=None,
    )
    with pytest.raises(CatalogError) as exc:
        create_product(
            db,
            business_id=business_id,
            actor_user_id=owner.user.id,
            sku="SKU-1",
            name="Duplicate",
            category_id=None,
            unit="each",
            cost=Decimal("1.00"),
            price=Decimal("2.00"),
            reorder_point=Decimal("1"),
            safety_stock=Decimal("0"),
            preferred_supplier_id=None,
        )
    assert exc.value.status_code == 409


def test_product_validation_rejects_negative_cost(db) -> None:
    owner = _owner(db)
    with pytest.raises(CatalogError) as exc:
        create_product(
            db,
            business_id=owner.user.business_id,
            actor_user_id=owner.user.id,
            sku="SKU-NEG",
            name="Bad Product",
            category_id=None,
            unit="each",
            cost=Decimal("-1.00"),
            price=Decimal("2.00"),
            reorder_point=Decimal("1"),
            safety_stock=Decimal("0"),
            preferred_supplier_id=None,
        )
    assert "Cost" in exc.value.message


def test_archive_product_soft_deletes(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id
    product = create_product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="SKU-ARCH",
        name="Spinach",
        category_id=None,
        unit="each",
        cost=Decimal("2.00"),
        price=Decimal("3.99"),
        reorder_point=Decimal("5"),
        safety_stock=Decimal("2"),
        preferred_supplier_id=None,
    )
    archived = archive_product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product.id,
    )
    assert archived.archived_at is not None
    items, total = list_products(
        db,
        business_id=business_id,
        search=None,
        category_id=None,
        page=1,
        page_size=10,
    )
    assert total == 0
    assert items == []
    assert db.scalar(select(func.count()).select_from(Product)) == 1


def test_list_products_search_filter_and_pagination(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id
    category = create_category(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        name="Dairy",
    )
    create_product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="MILK-1",
        name="Whole Milk",
        category_id=category.id,
        unit="each",
        cost=Decimal("2.40"),
        price=Decimal("4.29"),
        reorder_point=Decimal("10"),
        safety_stock=Decimal("5"),
        preferred_supplier_id=None,
    )
    create_product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="BREAD-1",
        name="Sourdough",
        category_id=None,
        unit="each",
        cost=Decimal("2.20"),
        price=Decimal("4.50"),
        reorder_point=Decimal("8"),
        safety_stock=Decimal("4"),
        preferred_supplier_id=None,
    )

    items, total = list_products(
        db,
        business_id=business_id,
        search="milk",
        category_id=category.id,
        page=1,
        page_size=1,
    )
    assert total == 1
    assert len(items) == 1
    assert items[0].sku == "MILK-1"
    assert items[0].category_name == "Dairy"


def test_tenant_isolation_for_catalog_entities(db) -> None:
    first = _owner(db)
    second = _other_owner(db)
    product = create_product(
        db,
        business_id=first.user.business_id,
        actor_user_id=first.user.id,
        sku="ISO-1",
        name="Isolated",
        category_id=None,
        unit="each",
        cost=Decimal("1.00"),
        price=Decimal("2.00"),
        reorder_point=Decimal("1"),
        safety_stock=Decimal("0"),
        preferred_supplier_id=None,
    )
    row = get_product_row(db, second.user.business_id, product.id)
    assert row is None


def test_update_product_with_preferred_supplier(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id
    supplier = create_supplier(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        name="Summit Beverage",
        email="buyers@summit.example",
        phone="555-0200",
        lead_time_days=3,
    )
    product = create_product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="WATER-1",
        name="Sparkling Water",
        category_id=None,
        unit="case",
        cost=Decimal("4.50"),
        price=Decimal("8.99"),
        reorder_point=Decimal("6"),
        safety_stock=Decimal("3"),
        preferred_supplier_id=supplier.id,
    )
    updated = update_product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product.id,
        sku="WATER-1",
        name="Sparkling Water 12pk",
        category_id=None,
        unit="case",
        cost=Decimal("4.75"),
        price=Decimal("9.49"),
        reorder_point=Decimal("8"),
        safety_stock=Decimal("4"),
        preferred_supplier_id=supplier.id,
    )
    assert updated.name == "Sparkling Water 12pk"
    row = get_product_row(db, business_id, product.id)
    assert row is not None
    assert row.preferred_supplier_id == supplier.id
    assert row.preferred_supplier_name == "Summit Beverage"

def test_archived_product_and_supplier_can_be_restored(db) -> None:
    owner = _owner(db)
    business_id = owner.user.business_id
    supplier = create_supplier(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        name="Restorable Supplier",
        email=None,
        phone=None,
        lead_time_days=1,
    )
    product = create_product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="RESTORE-1",
        name="Restorable",
        category_id=None,
        unit="each",
        cost=Decimal("1.00"),
        price=Decimal("2.00"),
        reorder_point=None,
        safety_stock=None,
        preferred_supplier_id=None,
    )
    archive_product(db, business_id=business_id, actor_user_id=owner.user.id, product_id=product.id)
    archive_supplier(db, business_id=business_id, actor_user_id=owner.user.id, supplier_id=supplier.id)

    archived_rows, archived_total = list_products(
        db, business_id=business_id, search=None, category_id=None, page=1, page_size=10, archived=True
    )
    assert archived_total == 1 and archived_rows[0].id == product.id
    assert list_suppliers(db, business_id=business_id) == []

    restored = restore_product(db, business_id=business_id, actor_user_id=owner.user.id, product_id=product.id)
    assert restored.archived_at is None
    restore_supplier(db, business_id=business_id, actor_user_id=owner.user.id, supplier_id=supplier.id)
    assert [item.id for item in list_suppliers(db, business_id=business_id)] == [supplier.id]

    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.business_id == business_id)))
    assert {"product.restore", "supplier.restore"} <= actions
