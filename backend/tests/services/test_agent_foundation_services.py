from datetime import timedelta
from decimal import Decimal

from app.repositories import inventory as inventory_repo
from app.services.agent_suggestions import create_suggestion, list_suggestions
from app.services.auth import signup
from app.services.catalog import create_product, create_supplier
from app.services.inventory import post_movement
from app.services.purchase_orders import create_po, transition_po
from app.services.replenishment import reorder_recommendations
from app.services.supplier_reliability import get_supplier_reliability
from app.agents.runs import start_agent_run
from app.models.types import utcnow


def _owner(db, *, email: str, business_name: str):
    return signup(
        db,
        full_name="Ada Owner",
        email=email,
        password="correct-horse-1",
        business_name=business_name,
    )


def _location_id(db, business_id: str) -> str:
    return inventory_repo.list_locations(db, business_id)[0].id


def test_create_suggestion_is_pending_and_tenant_scoped(db) -> None:
    owner = _owner(db, email="sug-a@example.com", business_name="Sug A")
    other = _owner(db, email="sug-b@example.com", business_name="Sug B")
    run = start_agent_run(
        db,
        business_id=owner.user.business_id,
        agent_name="echo",
        actor_user_id=owner.user.id,
    )
    created = create_suggestion(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        run_id=run.id,
        suggestion_type="generic",
        payload={"title": "Check oats", "summary": "On-hand is low."},
    )
    assert created["status"] == "pending"
    assert created["suggestion_type"] == "generic"
    mine = list_suggestions(db, business_id=owner.user.business_id)
    theirs = list_suggestions(db, business_id=other.user.business_id)
    assert len(mine) == 1
    assert theirs == []


def test_reorder_recommendations_uses_on_hand_and_forecast(db) -> None:
    owner = _owner(db, email="repl@example.com", business_name="Repl Shop")
    business_id = owner.user.business_id
    location_id = _location_id(db, business_id)
    product = create_product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="OATS-1",
        name="Oats",
        category_id=None,
        unit="each",
        cost=Decimal("1.00"),
        price=Decimal("2.00"),
        reorder_point=Decimal("10"),
        safety_stock=Decimal("2"),
        preferred_supplier_id=None,
    )
    post_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product.id,
        location_id=location_id,
        movement_type="receipt",
        quantity=Decimal("3"),
        note="Opening",
    )
    rows = reorder_recommendations(db, business_id=business_id)
    assert len(rows) == 1
    assert rows[0]["sku"] == "OATS-1"
    assert rows[0]["on_hand"] == Decimal("3")
    assert rows[0]["recommended_quantity"] == Decimal("9")


def test_supplier_reliability_marks_overdue_orders(db) -> None:
    owner = _owner(db, email="rel@example.com", business_name="Rel Shop")
    business_id = owner.user.business_id
    supplier = create_supplier(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        name="Metro",
        email="metro@example.com",
        phone=None,
        lead_time_days=5,
    )
    product = create_product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="OIL-1",
        name="Oil",
        category_id=None,
        unit="each",
        cost=Decimal("4.00"),
        price=Decimal("6.00"),
        reorder_point=Decimal("4"),
        safety_stock=Decimal("0"),
        preferred_supplier_id=supplier.id,
    )
    yesterday = utcnow().date() - timedelta(days=1)
    created = create_po(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        supplier_id=supplier.id,
        expected_date=yesterday,
        location_id=None,
        notes=None,
        line_items=[{"product_id": product.id, "quantity": "2", "unit_cost": "4.00"}],
    )
    transition_po(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        purchase_order_id=created["id"],
        action="approve",
        actor_role="owner",
    )
    transition_po(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        purchase_order_id=created["id"],
        action="send",
        actor_role="owner",
    )
    rows = get_supplier_reliability(db, business_id=business_id)
    assert rows[0]["supplier_name"] == "Metro"
    assert rows[0]["overdue_count"] == 1
    assert rows[0]["lead_time_days"] == 5
    assert rows[0]["reliability_score"] == 0.0
