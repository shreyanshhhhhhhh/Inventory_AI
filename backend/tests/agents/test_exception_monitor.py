from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.agents.context import AgentContext
from app.agents.exception_monitor import ExceptionMonitorAgent
from app.agents.playbooks import PLAYBOOK_ACTIONS
from app.agents.runs import start_agent_run
from app.llm.gateway import LLMGateway
from app.llm.providers.fake import FakeProvider
from app.models import InventoryException, PurchaseOrder, StockMovement
from app.models.types import utcnow
from app.repositories import inventory as inventory_repo
from app.services.agent_suggestions import list_suggestions
from app.services.auth import signup
from app.services.catalog import create_product, create_product_supplier, create_supplier
from app.services.exceptions import list_open
from app.services.inventory import post_movement
from app.services.purchase_orders import create_po, transition_po
from tests.orchestrator.helpers import events_of, owner, run_chat


def _signup(db, email: str, shop: str):
    return signup(
        db,
        full_name="Ada Owner",
        email=email,
        password="correct-horse-1",
        business_name=shop,
    )


def _location(db, business_id: str) -> str:
    return inventory_repo.list_locations(db, business_id)[0].id


def _at(day_offset: int, hour: int = 0) -> datetime:
    today = utcnow().astimezone(timezone.utc).date()
    return datetime.combine(
        today + timedelta(days=day_offset),
        datetime.min.time().replace(hour=hour),
        tzinfo=timezone.utc,
    )


def _product(db, signed, sku: str, *, supplier_id: str | None = None, lead: int = 7) -> str:
    product = create_product(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        sku=sku,
        name=sku,
        category_id=None,
        unit="each",
        cost=Decimal("2.00"),
        price=Decimal("5.00"),
        reorder_point=Decimal("5"),
        safety_stock=Decimal("0"),
        preferred_supplier_id=None,
    )
    if supplier_id:
        create_product_supplier(
            db,
            business_id=signed.user.business_id,
            actor_user_id=signed.user.id,
            product_id=product.id,
            supplier_id=supplier_id,
            unit_cost=Decimal("1.00"),
            lead_time_days=lead,
            is_preferred=True,
        )
    return product.id


def _agent(db, signed, *, gateway: LLMGateway | None = None) -> ExceptionMonitorAgent:
    run = start_agent_run(
        db,
        business_id=signed.user.business_id,
        agent_name="exception_monitor",
        actor_user_id=signed.user.id,
    )
    context = AgentContext(
        session=db,
        business_id=signed.user.business_id,
        user_id=signed.user.id,
        role="owner",
        run_id=run.id,
    )
    agent = ExceptionMonitorAgent(gateway=gateway)
    agent.attach(context)
    return agent


def _stockout_seed(db, signed) -> str:
    business_id = signed.user.business_id
    location_id = _location(db, business_id)
    supplier = create_supplier(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        name="Acme",
        email=None,
        phone=None,
        lead_time_days=7,
    )
    product_id = _product(db, signed, "LOW-1", supplier_id=supplier.id, lead=7)
    post_movement(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        product_id=product_id,
        location_id=location_id,
        movement_type="adjustment",
        quantity=Decimal("40"),
        note="Opening balance",
        occurred_at=_at(-20),
    )
    for offset in range(-14, 0):
        post_movement(
            db,
            business_id=business_id,
            actor_user_id=signed.user.id,
            product_id=product_id,
            location_id=location_id,
            movement_type="sale",
            quantity=Decimal("2"),
            occurred_at=_at(offset),
        )
    return product_id


def test_scan_writes_exceptions_and_suggestions_without_ledger_writes(db) -> None:
    signed = _signup(db, "scan-write@example.com", "Scan Shop")
    _stockout_seed(db, signed)
    movements_before = db.scalar(
        select(func.count()).select_from(StockMovement).where(
            StockMovement.business_id == signed.user.business_id
        )
    )
    orders_before = db.scalar(
        select(func.count()).select_from(PurchaseOrder).where(
            PurchaseOrder.business_id == signed.user.business_id
        )
    )
    result = _agent(db, signed).typed_result("scan", {}, step_id="s1")
    assert result.status == "ok"
    assert result.card_type == "exception_list"
    types = {item["exception_type"] for item in result.data["items"]}
    assert "stockout_risk" in types
    open_rows = list_open(db, business_id=signed.user.business_id)
    assert open_rows
    suggestions = list_suggestions(db, business_id=signed.user.business_id)
    assert suggestions
    assert suggestions[0]["payload"]["extra"]["action"] in PLAYBOOK_ACTIONS
    movements_after = db.scalar(
        select(func.count()).select_from(StockMovement).where(
            StockMovement.business_id == signed.user.business_id
        )
    )
    orders_after = db.scalar(
        select(func.count()).select_from(PurchaseOrder).where(
            PurchaseOrder.business_id == signed.user.business_id
        )
    )
    assert movements_after == movements_before
    assert orders_after == orders_before


def test_dedupe_does_not_recreate_open_exceptions(db) -> None:
    signed = _signup(db, "scan-dedupe@example.com", "Dedupe Shop")
    _stockout_seed(db, signed)
    first = _agent(db, signed).typed_result("scan", {}, step_id="s1")
    second = _agent(db, signed).typed_result("scan", {}, step_id="s2")
    assert first.data["items"]
    keys = [item["dedupe_key"] for item in first.data["items"]]
    assert [item["dedupe_key"] for item in second.data["items"]] == keys
    count = db.scalar(
        select(func.count()).select_from(InventoryException).where(
            InventoryException.business_id == signed.user.business_id
        )
    )
    assert int(count or 0) == len(keys)
    suggestions = list_suggestions(db, business_id=signed.user.business_id)
    assert len(suggestions) == len([item for item in first.data["items"] if item["recommended_action"] != "ignore"])


def test_llm_cannot_select_action_outside_playbook(db) -> None:
    signed = _signup(db, "scan-clip@example.com", "Clip Shop")
    _stockout_seed(db, signed)
    gateway = LLMGateway(
        db,
        provider=FakeProvider(
            scripts={
                "exception_rank": {
                    "text": '{"rankings":[{"dedupe_key":"stockout_risk:ignore-me","action":"hack_the_ledger","rationale":"nope"}]}'
                }
            }
        ),
    )
    result = _agent(db, signed, gateway=gateway).typed_result("scan", {}, step_id="s1")
    actions = {item["recommended_action"] for item in result.data["items"]}
    assert "hack_the_ledger" not in actions
    assert actions <= PLAYBOOK_ACTIONS


def test_scan_is_tenant_scoped(db) -> None:
    shop_a = _signup(db, "scan-a@example.com", "Scan A")
    shop_b = _signup(db, "scan-b@example.com", "Scan B")
    _stockout_seed(db, shop_b)
    result_a = _agent(db, shop_a).typed_result("scan", {}, step_id="s1")
    assert result_a.data["items"] == []
    assert list_open(db, business_id=shop_a.user.business_id) == []
    result_b = _agent(db, shop_b).typed_result("scan", {}, step_id="s2")
    assert result_b.data["items"]
    assert list_open(db, business_id=shop_a.user.business_id) == []
    assert all(item["id"] for item in list_open(db, business_id=shop_b.user.business_id))


def test_supplier_delay_from_overdue_po(db) -> None:
    signed = _signup(db, "scan-po@example.com", "PO Shop")
    business_id = signed.user.business_id
    location_id = _location(db, business_id)
    supplier = create_supplier(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        name="Late Co",
        email=None,
        phone=None,
        lead_time_days=3,
    )
    product_id = _product(db, signed, "PO-SKU", supplier_id=supplier.id, lead=3)
    post_movement(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        product_id=product_id,
        location_id=location_id,
        movement_type="adjustment",
        quantity=Decimal("50"),
        note="Opening balance",
        occurred_at=_at(-10),
    )
    order = create_po(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        supplier_id=supplier.id,
        expected_date=date(2020, 1, 1),
        location_id=location_id,
        notes=None,
        line_items=[{"product_id": product_id, "quantity": Decimal("4"), "unit_cost": Decimal("1.00")}],
    )
    transition_po(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        purchase_order_id=order["id"],
        action="approve",
        actor_role="owner",
    )
    result = _agent(db, signed).typed_result("scan", {}, step_id="s1")
    types = {item["exception_type"] for item in result.data["items"]}
    assert "supplier_delay" in types


def test_chat_scan_emits_exception_list(db) -> None:
    signed = owner(db, "scan-chat@example.com", "Chat Scan")
    run = run_chat(db, signed, "/scan")
    cards = events_of(run, "card")
    assert cards[0].payload["card"]["type"] == "exception_list"
    assert cards[0].payload["card"]["status"] == "ok"
