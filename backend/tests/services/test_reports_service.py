from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.models.types import utcnow
from app.repositories import inventory as inventory_repo
from app.services.catalog import create_product, create_supplier
from app.services.inventory import post_movement, record_movement
from app.services.purchase_orders import create_po, transition_po
from app.services.reports import (
    get_accounts_by_supplier,
    get_accounts_summary,
    get_movements_over_time,
    get_top_sellers,
)
from tests.helpers.tenant import signup_service_tenant


def _owner(db, *, email: str, business_name: str):
    return signup_service_tenant(
        db,
        full_name="Ada Owner",
        email=email,
        password="correct-horse-1",
        business_name=business_name,
    )


def _default_location_id(db, business_id: str) -> str:
    return inventory_repo.list_locations(db, business_id)[0].id


def _product(
    db,
    *,
    business_id: str,
    actor_user_id: str,
    sku: str,
    cost: str = "2.00",
) -> str:
    supplier = create_supplier(
        db,
        business_id=business_id,
        actor_user_id=actor_user_id,
        name=f"Supplier for {sku}",
        email=None,
        phone=None,
        lead_time_days=1,
    )
    product = create_product(
        db,
        business_id=business_id,
        actor_user_id=actor_user_id,
        sku=sku,
        name=f"Product {sku}",
        category_id=None,
        unit="each",
        cost=Decimal(cost),
        price=Decimal("5.00"),
        reorder_point=Decimal("5"),
        safety_stock=Decimal("0"),
        preferred_supplier_id=supplier.id,
    )
    return product.id


def test_empty_business_returns_zeros_and_empty_series(db) -> None:
    owner = _owner(db, email="reports-empty@example.com", business_name="Empty Reports")
    business_id = owner.user.business_id

    summary = get_accounts_summary(db, business_id=business_id)
    assert summary["stock_value"] == Decimal("0")
    assert summary["open_po_value"] == Decimal("0")
    assert summary["payables_due"] == Decimal("0")
    assert get_accounts_by_supplier(db, business_id=business_id) == []

    movement_series = get_movements_over_time(db, business_id=business_id, days=7)
    assert movement_series["days"] == 7
    assert len(movement_series["items"]) == 7
    assert all(
        item["units_in"] == Decimal("0") and item["units_out"] == Decimal("0")
        for item in movement_series["items"]
    )

    top_sellers = get_top_sellers(db, business_id=business_id, days=30, limit=5)
    assert top_sellers["items"] == []


def test_known_dataset_and_date_range(db) -> None:
    owner = _owner(db, email="reports-known@example.com", business_name="Reports Shop")
    business_id = owner.user.business_id
    location_id = _default_location_id(db, business_id)

    product_a = _product(db, business_id=business_id, actor_user_id=owner.user.id, sku="TOP-A", cost="3.00")
    product_b = _product(db, business_id=business_id, actor_user_id=owner.user.id, sku="TOP-B", cost="4.00")

    today = utcnow().astimezone(timezone.utc).date()
    in_window = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    out_of_window = datetime.combine(
        today - timedelta(days=40),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )

    record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_a,
        location_id=location_id,
        movement_type="receipt",
        quantity=Decimal("10"),
        occurred_at=in_window,
    )
    post_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_a,
        location_id=location_id,
        movement_type="sale",
        quantity=Decimal("4"),
        occurred_at=in_window,
    )
    record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_b,
        location_id=location_id,
        movement_type="receipt",
        quantity=Decimal("5"),
        occurred_at=in_window,
    )
    post_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_b,
        location_id=location_id,
        movement_type="sale",
        quantity=Decimal("2"),
        occurred_at=in_window,
    )
    post_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_a,
        location_id=location_id,
        movement_type="receipt",
        quantity=Decimal("100"),
        occurred_at=out_of_window,
    )
    post_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_a,
        location_id=location_id,
        movement_type="sale",
        quantity=Decimal("99"),
        occurred_at=out_of_window,
    )

    series = get_movements_over_time(db, business_id=business_id, days=30)
    today_point = next(item for item in series["items"] if item["date"] == today)
    assert today_point["units_in"] == Decimal("15")
    assert today_point["units_out"] == Decimal("6")

    top_sellers = get_top_sellers(db, business_id=business_id, days=30, limit=5)
    assert len(top_sellers["items"]) == 2
    assert top_sellers["items"][0]["product_id"] == product_a
    assert top_sellers["items"][0]["units_sold"] == Decimal("4")
    assert top_sellers["items"][1]["units_sold"] == Decimal("2")

    summary = get_accounts_summary(db, business_id=business_id)
    # Product A: 7 on hand × $3; Product B: 3 on hand × $4
    assert summary["stock_value"] == Decimal("33.00")

    supplier = create_supplier(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        name="Valley Foods",
        email=None,
        phone=None,
        lead_time_days=2,
    )
    draft_po = create_po(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        supplier_id=supplier.id,
        expected_date=date(2026, 10, 1),
        location_id=location_id,
        notes=None,
        line_items=[{"product_id": product_a, "quantity": "2", "unit_cost": "3.00"}],
    )
    approved_po = create_po(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        supplier_id=supplier.id,
        expected_date=date(2026, 10, 2),
        location_id=location_id,
        notes=None,
        line_items=[{"product_id": product_b, "quantity": "1", "unit_cost": "4.00"}],
    )
    transition_po(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        actor_role="owner",
        purchase_order_id=approved_po["id"],
        action="approve",
    )

    summary = get_accounts_summary(db, business_id=business_id)
    assert summary["open_po_value"] == Decimal("10.00")
    assert summary["payables_due"] == Decimal("4.00")

    by_supplier = get_accounts_by_supplier(db, business_id=business_id)
    assert len(by_supplier) == 2
    draft_row = next(row for row in by_supplier if row["status"] == "draft")
    approved_row = next(row for row in by_supplier if row["status"] == "approved")
    assert draft_row["total"] == Decimal("6.00")
    assert draft_row["purchase_order_count"] == 1
    assert approved_row["total"] == Decimal("4.00")
    assert draft_po["id"]  # referenced to avoid unused warning


def test_tenant_isolation(db) -> None:
    owner_a = _owner(db, email="reports-a@example.com", business_name="Reports A")
    owner_b = _owner(db, email="reports-b@example.com", business_name="Reports B")
    location_a = _default_location_id(db, owner_a.user.business_id)
    product_a = _product(
        db,
        business_id=owner_a.user.business_id,
        actor_user_id=owner_a.user.id,
        sku="ISO-A",
        cost="5.00",
    )
    record_movement(
        db,
        business_id=owner_a.user.business_id,
        actor_user_id=owner_a.user.id,
        product_id=product_a,
        location_id=location_a,
        movement_type="receipt",
        quantity=Decimal("4"),
    )

    summary_b = get_accounts_summary(db, business_id=owner_b.user.business_id)
    assert summary_b["stock_value"] == Decimal("0")
    assert get_top_sellers(db, business_id=owner_b.user.business_id, days=30, limit=5) == {
        "days": 30,
        "limit": 5,
        "items": [],
    }

    summary_a = get_accounts_summary(db, business_id=owner_a.user.business_id)
    assert summary_a["stock_value"] == Decimal("20.00")
