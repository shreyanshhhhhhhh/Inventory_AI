import json
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.agents.context import AgentContext
from app.agents.replenishment import ReplenishmentAgent
from app.agents.runs import start_agent_run
from app.models import PurchaseOrder
from app.models.types import utcnow
from app.orchestrator.engine import resume_chat_run
from app.repositories import inventory as inventory_repo
from app.services.agent_suggestions import list_suggestions
from app.services.catalog import create_product, create_product_supplier, create_supplier
from app.services.inventory import post_movement
from app.services.purchase_orders import create_po, transition_po
from app.services.team import create_staff_user
from tests.orchestrator.helpers import events_of, owner, run_chat


def _location_id(db, business_id: str) -> str:
    return inventory_repo.list_locations(db, business_id)[0].id


def _po_count(db, business_id: str) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(PurchaseOrder)
            .where(PurchaseOrder.business_id == business_id)
        )
        or 0
    )


def _product(db, *, business_id: str, actor_user_id: str, sku: str, name: str, reorder: str, safety: str = "0"):
    return create_product(
        db,
        business_id=business_id,
        actor_user_id=actor_user_id,
        sku=sku,
        name=name,
        category_id=None,
        unit="each",
        cost=Decimal("1.00"),
        price=Decimal("2.00"),
        reorder_point=Decimal(reorder),
        safety_stock=Decimal(safety),
        preferred_supplier_id=None,
    )


def _link(db, *, business_id: str, actor_user_id: str, product_id: str, supplier_id: str, cost: str, preferred: bool):
    return create_product_supplier(
        db,
        business_id=business_id,
        actor_user_id=actor_user_id,
        product_id=product_id,
        supplier_id=supplier_id,
        unit_cost=Decimal(cost),
        lead_time_days=3,
        is_preferred=preferred,
    )


def _receive(db, *, business_id: str, actor_user_id: str, product_id: str, quantity: str) -> None:
    post_movement(
        db,
        business_id=business_id,
        actor_user_id=actor_user_id,
        product_id=product_id,
        location_id=_location_id(db, business_id),
        movement_type="receipt",
        quantity=Decimal(quantity),
        note="Opening",
    )


def _agent(db, signed, *, role: str = "owner", user_id: str | None = None) -> ReplenishmentAgent:
    run = start_agent_run(
        db,
        business_id=signed.user.business_id,
        agent_name="replenishment",
        actor_user_id=user_id or signed.user.id,
    )
    agent = ReplenishmentAgent()
    agent.attach(
        AgentContext(
            session=db,
            business_id=signed.user.business_id,
            user_id=user_id or signed.user.id,
            role=role,
            run_id=run.id,
        )
    )
    return agent


def _oats(db, signed, *, name: str = "Oats", reorder: str = "10", safety: str = "2", on_hand: str = "3"):
    supplier = create_supplier(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        name="Mill",
        email="mill@example.com",
        phone=None,
        lead_time_days=4,
    )
    product = _product(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        sku="OATS-1",
        name=name,
        reorder=reorder,
        safety=safety,
    )
    _link(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        product_id=product.id,
        supplier_id=supplier.id,
        cost="1.00",
        preferred=True,
    )
    _receive(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        product_id=product.id,
        quantity=on_hand,
    )
    return supplier, product


def test_agent_draft_uses_only_recommendation_numbers(db) -> None:
    signed = owner(db, "repl-real@example.com", "Real Shop")
    supplier, product = _oats(db, signed, name="invent_qty oats")
    result = _agent(db, signed).typed_result("draft_po", {}, step_id="draft")
    blob = json.dumps(result.data) + result.message
    assert "99999" not in blob
    assert "HACK" not in blob
    assert "not-a-real-id" not in blob
    assert result.data["reason_codes"] == ["LOW_COVER"]
    assert result.data["lines"][0]["sku"] == "OATS-1"
    assert Decimal(result.data["lines"][0]["quantity"]) == Decimal("9")
    assert Decimal(result.data["evidence"][0]["recommended_quantity"]) == Decimal("9")
    assert Decimal(result.data["evidence"][0]["on_hand"]) == Decimal("3")
    suggestions = list_suggestions(db, business_id=signed.user.business_id)
    assert len(suggestions) == 1
    assert suggestions[0]["status"] == "pending"
    assert suggestions[0]["payload"]["supplier_id"] == supplier.id
    assert Decimal(suggestions[0]["payload"]["lines"][0]["quantity"]) == Decimal("9")
    assert _po_count(db, signed.user.business_id) == 0
    del product


def test_recommend_does_not_write_and_low_confidence_asks(db) -> None:
    signed = owner(db, "repl-low@example.com", "Low Shop")
    _oats(db, signed, name="low_confidence_reorder")
    agent = _agent(db, signed)
    recommend = agent.typed_result("recommend", {}, step_id="rec")
    assert recommend.card_type == "text"
    assert list_suggestions(db, business_id=signed.user.business_id) == []

    agent = _agent(db, signed)
    draft = agent.typed_result("draft_po", {}, step_id="draft")
    assert draft.card_type == "text"
    assert "not confident" in draft.message.lower()
    assert list_suggestions(db, business_id=signed.user.business_id) == []
    assert _po_count(db, signed.user.business_id) == 0


def test_missing_supplier_asks_and_does_not_suggest(db) -> None:
    signed = owner(db, "repl-miss@example.com", "Miss Shop")
    product = _product(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        sku="OATS-1",
        name="Oats",
        reorder="10",
        safety="2",
    )
    _receive(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        product_id=product.id,
        quantity="3",
    )
    result = _agent(db, signed).typed_result("draft_po", {}, step_id="draft")
    assert "OATS-1" in result.message
    assert "supplier" in result.message.lower()
    assert list_suggestions(db, business_id=signed.user.business_id) == []
    assert _po_count(db, signed.user.business_id) == 0


def test_fractional_recommendation_is_not_rounded(db) -> None:
    signed = owner(db, "repl-frac@example.com", "Frac Shop")
    _oats(db, signed, reorder="10.5", safety="0", on_hand="3")
    result = _agent(db, signed).typed_result("draft_po", {}, step_id="draft")
    assert "whole number" in result.message
    assert "7.5" in result.message
    assert "8" not in result.message
    assert list_suggestions(db, business_id=signed.user.business_id) == []


def test_open_po_cover_and_rejected_path_leave_no_extra_po(db) -> None:
    signed = owner(db, "repl-cover@example.com", "Cover Shop")
    supplier, product = _oats(db, signed)
    create_po(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        supplier_id=supplier.id,
        expected_date=None,
        location_id=None,
        notes=None,
        line_items=[{"product_id": product.id, "quantity": "9", "unit_cost": "1.00"}],
    )
    result = _agent(db, signed).typed_result("draft_po", {}, step_id="draft")
    assert "already cover" in result.message
    assert list_suggestions(db, business_id=signed.user.business_id) == []
    assert _po_count(db, signed.user.business_id) == 1


def test_late_preferred_supplier_can_switch_to_a_linked_alternate(db) -> None:
    signed = owner(db, "repl-alt@example.com", "Alt Shop")
    business_id = signed.user.business_id
    slow = create_supplier(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        name="Slow Co",
        email="slow@example.com",
        phone=None,
        lead_time_days=14,
    )
    fast = create_supplier(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        name="Fast Co",
        email="fast@example.com",
        phone=None,
        lead_time_days=2,
    )
    oats = _product(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        sku="OATS-1",
        name="Rolled oats",
        reorder="10",
        safety="2",
    )
    filler = _product(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        sku="FILL-1",
        name="Filler",
        reorder="0",
        safety="0",
    )
    _link(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        product_id=oats.id,
        supplier_id=slow.id,
        cost="4.00",
        preferred=True,
    )
    _link(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        product_id=oats.id,
        supplier_id=fast.id,
        cost="1.50",
        preferred=False,
    )
    _receive(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        product_id=oats.id,
        quantity="3",
    )
    late = create_po(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        supplier_id=slow.id,
        expected_date=utcnow().date() - timedelta(days=2),
        location_id=None,
        notes=None,
        line_items=[{"product_id": filler.id, "quantity": "1", "unit_cost": "1.00"}],
    )
    transition_po(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        purchase_order_id=str(late["id"]),
        action="approve",
        actor_role="owner",
    )
    transition_po(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        purchase_order_id=str(late["id"]),
        action="send",
        actor_role="owner",
    )
    result = _agent(db, signed).typed_result("draft_po", {}, step_id="draft")
    suggestions = list_suggestions(db, business_id=business_id)
    assert len(suggestions) == 1
    assert suggestions[0]["payload"]["supplier_id"] == fast.id
    assert Decimal(suggestions[0]["payload"]["lines"][0]["unit_cost"]) == Decimal("1.50")
    assert "ALTERNATE_SUPPLIER" in suggestions[0]["payload"]["reason_codes"]
    assert "SUPPLIER_LATE" in suggestions[0]["payload"]["reason_codes"]
    assert "LOW_COVER" in suggestions[0]["payload"]["reason_codes"]
    assert result.data["suggestion_id"] == suggestions[0]["id"]
    assert _po_count(db, business_id) == 1


def test_named_supplier_draft_and_staff_cannot_write(db) -> None:
    signed = owner(db, "repl-named@example.com", "Named Shop")
    supplier, _product_row = _oats(db, signed)
    other = create_supplier(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        name="Other Mill",
        email="other@example.com",
        phone=None,
        lead_time_days=1,
    )
    missing = _agent(db, signed).typed_result(
        "draft_po",
        {"supplier_id": other.id},
        step_id="draft",
    )
    assert "not linked" in missing.message
    assert list_suggestions(db, business_id=signed.user.business_id) == []

    drafted = _agent(db, signed).typed_result(
        "draft_po",
        {"supplier_id": supplier.id},
        step_id="draft-named",
    )
    assert drafted.card_type == "po_suggestion"
    stored = list_suggestions(db, business_id=signed.user.business_id)
    assert stored[0]["payload"]["supplier_id"] == supplier.id

    staff = create_staff_user(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        full_name="Sam Staff",
        email="repl-staff@example.com",
        temporary_password="staff-pass-123",
    )
    before = len(stored)
    blocked = _agent(db, signed, role="staff", user_id=str(staff["id"])).typed_result(
        "draft_po",
        {},
        step_id="staff",
    )
    assert blocked.status == "failed"
    assert len(list_suggestions(db, business_id=signed.user.business_id)) == before
    assert _po_count(db, signed.user.business_id) == 0


def test_tenant_isolation_and_slash_draft(db) -> None:
    signed = owner(db, "repl-a@example.com", "Shop A")
    other = owner(db, "repl-b@example.com", "Shop B")
    _oats(db, signed)
    _product(
        db,
        business_id=other.user.business_id,
        actor_user_id=other.user.id,
        sku="SECRET-1",
        name="Secret",
        reorder="5",
        safety="0",
    )
    result = _agent(db, signed).typed_result("draft_po", {}, step_id="draft")
    blob = json.dumps(result.data) + result.message
    assert "SECRET-1" not in blob
    mine = list_suggestions(db, business_id=signed.user.business_id)
    assert len(mine) == 1
    assert mine[0]["business_id"] == signed.user.business_id
    assert list_suggestions(db, business_id=other.user.business_id) == []

    run = run_chat(db, signed, "/reorder")
    cards = events_of(run, "card")
    assert cards
    assert "not implemented" not in cards[0].payload["card"]["message"].lower()

    paused = run_chat(db, signed, "/draft-po Mill")
    assert paused.status == "awaiting_approval"
    resumed = resume_chat_run(
        db,
        business_id=signed.user.business_id,
        user_id=signed.user.id,
        run_id=paused.id,
        action="run",
        background=False,
    )
    assert resumed.status == "completed"
    drafted = [
        row
        for row in list_suggestions(db, business_id=signed.user.business_id)
        if row["run_id"] == resumed.id
    ]
    assert drafted
    assert "Mill" in json.dumps(drafted[0]["payload"]) or drafted[0]["payload"]["supplier_id"]
