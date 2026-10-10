from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.agents.context import AgentContext
from app.agents.forecast import ForecastAgent
from app.agents.runs import start_agent_run
from app.llm.gateway import LLMGateway
from app.llm.providers.fake import FakeProvider
from app.models import PurchaseOrder, StockMovement
from app.models.types import utcnow
from app.repositories import inventory as inventory_repo
from app.services.auth import signup
from app.services.catalog import create_product
from app.services.inventory import post_movement
from tests.orchestrator.helpers import events_of, owner, run_chat


def _signup(db, email: str, shop: str):
    return signup(
        db,
        full_name="Ada Owner",
        email=email,
        password="correct-horse-1",
        business_name=shop,
    )


def _location_id(db, business_id: str) -> str:
    return inventory_repo.list_locations(db, business_id)[0].id


def _product(db, *, business_id: str, actor_user_id: str, sku: str, name: str) -> str:
    product = create_product(
        db,
        business_id=business_id,
        actor_user_id=actor_user_id,
        sku=sku,
        name=name,
        category_id=None,
        unit="each",
        cost=Decimal("2.00"),
        price=Decimal("5.00"),
        reorder_point=Decimal("5"),
        safety_stock=Decimal("0"),
        preferred_supplier_id=None,
    )
    return product.id


def _at(day_offset: int) -> datetime:
    today = utcnow().astimezone(timezone.utc).date()
    return datetime.combine(today + timedelta(days=day_offset), datetime.min.time(), tzinfo=timezone.utc)


def _sell(db, *, business_id: str, actor_user_id: str, product_id: str, location_id: str, quantity: str) -> None:
    post_movement(
        db,
        business_id=business_id,
        actor_user_id=actor_user_id,
        product_id=product_id,
        location_id=location_id,
        movement_type="adjustment",
        quantity=Decimal("20"),
        note="Opening balance",
        occurred_at=_at(-3),
    )
    post_movement(
        db,
        business_id=business_id,
        actor_user_id=actor_user_id,
        product_id=product_id,
        location_id=location_id,
        movement_type="sale",
        quantity=Decimal(quantity),
        occurred_at=_at(-1),
    )


def _agent(db, signed, *, gateway: LLMGateway | None = None) -> ForecastAgent:
    run = start_agent_run(
        db,
        business_id=signed.user.business_id,
        agent_name="forecast",
        actor_user_id=signed.user.id,
    )
    context = AgentContext(
        session=db,
        business_id=signed.user.business_id,
        user_id=signed.user.id,
        role="owner",
        run_id=run.id,
    )
    agent = ForecastAgent(gateway=gateway)
    agent.attach(context)
    return agent


def test_stock_task_returns_table_from_ledger(db) -> None:
    signed = _signup(db, "forecast-stock@example.com", "Stock Shop")
    business_id = signed.user.business_id
    location_id = _location_id(db, business_id)
    product_id = _product(db, business_id=business_id, actor_user_id=signed.user.id, sku="FLOUR-1KG", name="Flour")
    post_movement(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        product_id=product_id,
        location_id=location_id,
        movement_type="adjustment",
        quantity=Decimal("12"),
        note="Opening balance",
        occurred_at=_at(-2),
    )
    agent = _agent(db, signed)
    result = agent.typed_result("get_stock", {}, step_id="s1")
    assert result.status == "ok"
    assert result.card_type == "stock_table"
    assert result.data["items"][0]["sku"] == "FLOUR-1KG"
    assert result.data["items"][0]["on_hand"] == "12.0000"
    assert str(result.data["total"]) in result.message


def test_forecast_typed_output_comes_from_tools_not_llm_math(db) -> None:
    signed = _signup(db, "forecast-chart@example.com", "Chart Shop")
    business_id = signed.user.business_id
    location_id = _location_id(db, business_id)
    product_id = _product(db, business_id=business_id, actor_user_id=signed.user.id, sku="RICE-1KG", name="Rice")
    _sell(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        product_id=product_id,
        location_id=location_id,
        quantity="3",
    )
    agent = _agent(db, signed)
    result = agent.typed_result("forecast", {"product_id": product_id}, step_id="s1")
    assert result.status == "ok"
    assert result.card_type == "forecast_chart"
    item = result.data["items"][0]
    assert item["sku"] == "RICE-1KG"
    assert item["trend"] in {"up", "down", "flat"}
    assert item["chosen_model"] in {"no_sales", "daily_average", "seasonal_naive"}
    assert item["confidence"] in {"high", "medium", "low"}
    assert "low_history" in item["caveats"]
    assert result.data["horizon_days"] == 14
    assert len(result.data["points"]) == 14
    assert result.data["accuracy"][0]["chosen_model"] == item["chosen_model"]
    assert "99999" not in result.message


def test_ungrounded_llm_interpretation_is_replaced_with_template(db) -> None:
    signed = _signup(db, "forecast-ungrounded@example.com", "Ground Shop")
    business_id = signed.user.business_id
    location_id = _location_id(db, business_id)
    product_id = _product(db, business_id=business_id, actor_user_id=signed.user.id, sku="TEA", name="Tea")
    _sell(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        product_id=product_id,
        location_id=location_id,
        quantity="2",
    )
    gateway = LLMGateway(
        db,
        provider=FakeProvider(
            scripts={
                "forecast_interpret": {
                    "text": '{"interpretation":"There are 99999 units of demand."}'
                }
            }
        ),
    )
    agent = _agent(db, signed, gateway=gateway)
    result = agent.typed_result("forecast", {"product_id": product_id}, step_id="s1")
    assert "99999" not in result.message
    assert "TEA" in result.message
    assert result.data["items"][0]["chosen_model"] in result.message


def test_forecast_does_not_write_orders_or_ledger(db) -> None:
    signed = _signup(db, "forecast-ro@example.com", "Read Shop")
    business_id = signed.user.business_id
    movements_before = db.scalar(select(func.count()).select_from(StockMovement).where(StockMovement.business_id == business_id))
    orders_before = db.scalar(select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.business_id == business_id))
    agent = _agent(db, signed)
    agent.typed_result("forecast", {}, step_id="s1")
    agent.typed_result("get_stock", {}, step_id="s2")
    movements_after = db.scalar(select(func.count()).select_from(StockMovement).where(StockMovement.business_id == business_id))
    orders_after = db.scalar(select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.business_id == business_id))
    assert movements_after == movements_before
    assert orders_after == orders_before


def test_forecast_is_tenant_scoped(db) -> None:
    shop_a = _signup(db, "forecast-a@example.com", "Shop A")
    shop_b = _signup(db, "forecast-b@example.com", "Shop B")
    product_b = _product(
        db,
        business_id=shop_b.user.business_id,
        actor_user_id=shop_b.user.id,
        sku="OTHER-SKU",
        name="Other",
    )
    agent_a = _agent(db, shop_a)
    listed = agent_a.typed_result("forecast", {}, step_id="s1")
    assert listed.data["items"] == []
    missing = agent_a.typed_result("forecast", {"product_id": product_b}, step_id="s2")
    assert missing.status == "failed"


def test_chat_forecast_and_stock_emit_typed_cards(db) -> None:
    signed = owner(db, "forecast-chat@example.com", "Chat Forecast")
    forecast_run = run_chat(db, signed, "/forecast")
    forecast_cards = events_of(forecast_run, "card")
    assert forecast_cards[0].payload["card"]["type"] == "forecast_chart"
    assert forecast_cards[0].payload["card"]["status"] == "ok"
    stock_run = run_chat(db, signed, "/stock")
    stock_cards = events_of(stock_run, "card")
    assert stock_cards[0].payload["card"]["type"] == "stock_table"
    assert stock_cards[0].payload["card"]["status"] == "ok"
