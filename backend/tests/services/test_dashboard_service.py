from datetime import date, datetime, timezone
from decimal import Decimal

from app.repositories import inventory as inventory_repo
from app.services.auth import signup
from app.services.catalog import create_product, create_supplier
from app.services.dashboard import get_activity, get_needs_attention, get_summary
from app.services.inventory import get_stock_levels, post_movement, record_movement
from app.services.purchase_orders import create_po, transition_po


def _owner(db, *, email: str, business_name: str):
    return signup(
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
    cost: str,
    reorder_point: str,
) -> str:
    product = create_product(
        db,
        business_id=business_id,
        actor_user_id=actor_user_id,
        sku=sku,
        name=f"Product {sku}",
        category_id=None,
        unit="each",
        cost=Decimal(cost),
        price=Decimal("9.99"),
        reorder_point=Decimal(reorder_point),
        safety_stock=Decimal("0"),
        preferred_supplier_id=None,
    )
    return product.id


def test_empty_business_returns_zeros(db) -> None:
    owner = _owner(db, email="dash-empty@example.com", business_name="Empty Dash")
    business_id = owner.user.business_id

    summary = get_summary(db, business_id=business_id)
    assert summary["total_stock_value"] == Decimal("0")
    assert summary["low_stock_count"] == 0
    assert summary["open_purchase_orders"] == 0
    assert summary["pending_approvals"] == 0
    assert summary["open_exceptions"] == 0
    assert get_needs_attention(db, business_id=business_id) == []
    assert get_activity(db, business_id=business_id) == []


def test_summary_matches_known_dataset(db) -> None:
    owner = _owner(db, email="dash-known@example.com", business_name="Dash Shop")
    business_id = owner.user.business_id
    location_id = _default_location_id(db, business_id)

    product_a = _product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="A-1",
        cost="2.00",
        reorder_point="10",
    )
    product_b = _product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="B-1",
        cost="3.00",
        reorder_point="20",
    )

    record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_a,
        location_id=location_id,
        movement_type="receipt",
        quantity=Decimal("8"),
    )
    record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_b,
        location_id=location_id,
        movement_type="receipt",
        quantity=Decimal("5"),
    )

    stock_items, stock_total = get_stock_levels(
        db,
        business_id=business_id,
        low_only=True,
        page=1,
        page_size=100,
    )
    assert stock_total == 2

    summary = get_summary(db, business_id=business_id)
    assert summary["total_stock_value"] == Decimal("31.00")
    assert summary["low_stock_count"] == stock_total

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
        line_items=[{"product_id": product_a, "quantity": "1", "unit_cost": "2.00"}],
    )
    approved_po = create_po(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        supplier_id=supplier.id,
        expected_date=date(2026, 10, 2),
        location_id=location_id,
        notes=None,
        line_items=[{"product_id": product_b, "quantity": "1", "unit_cost": "3.00"}],
    )
    transition_po(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        actor_role="owner",
        purchase_order_id=approved_po["id"],
        action="approve",
    )
    received_po = create_po(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        supplier_id=supplier.id,
        expected_date=date(2026, 10, 3),
        location_id=location_id,
        notes=None,
        line_items=[{"product_id": product_a, "quantity": "1", "unit_cost": "2.00"}],
    )
    transition_po(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        actor_role="owner",
        purchase_order_id=received_po["id"],
        action="approve",
    )
    transition_po(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        actor_role="owner",
        purchase_order_id=received_po["id"],
        action="send",
    )
    transition_po(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        actor_role="owner",
        purchase_order_id=received_po["id"],
        action="receive",
    )

    summary = get_summary(db, business_id=business_id)
    assert summary["open_purchase_orders"] == 2

    needs_attention = get_needs_attention(db, business_id=business_id)
    assert len(needs_attention) == 2
    assert [item["on_hand"] for item in needs_attention] == [Decimal("5"), Decimal("9")]
    assert all(item["status"] == "low" for item in needs_attention)

    post_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_a,
        location_id=location_id,
        movement_type="sale",
        quantity=Decimal("8"),
        occurred_at=datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc),
    )
    transition_po(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        actor_role="owner",
        purchase_order_id=draft_po["id"],
        action="approve",
    )

    activity = get_activity(db, business_id=business_id, limit=10)
    assert len(activity) >= 2
    assert activity[0]["kind"] == "purchase_order_status"
    assert activity[0]["title"] == draft_po["po_number"]
    assert activity[0]["subtitle"] == "Approved"
    assert any(item["kind"] == "movement" for item in activity)


def test_tenant_isolation(db) -> None:
    owner_a = _owner(db, email="dash-a@example.com", business_name="Dash A")
    owner_b = _owner(db, email="dash-b@example.com", business_name="Dash B")
    location_a = _default_location_id(db, owner_a.user.business_id)
    product_a = _product(
        db,
        business_id=owner_a.user.business_id,
        actor_user_id=owner_a.user.id,
        sku="ISO-A",
        cost="4.00",
        reorder_point="5",
    )
    record_movement(
        db,
        business_id=owner_a.user.business_id,
        actor_user_id=owner_a.user.id,
        product_id=product_a,
        location_id=location_a,
        movement_type="receipt",
        quantity=Decimal("3"),
    )

    summary_b = get_summary(db, business_id=owner_b.user.business_id)
    assert summary_b["total_stock_value"] == Decimal("0")
    assert summary_b["low_stock_count"] == 0
    assert get_needs_attention(db, business_id=owner_b.user.business_id) == []

    summary_a = get_summary(db, business_id=owner_a.user.business_id)
    assert summary_a["total_stock_value"] == Decimal("12.00")
    assert summary_a["low_stock_count"] == 1
