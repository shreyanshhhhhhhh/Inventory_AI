from decimal import Decimal

from app.agents.context import AgentContext
from app.agents.errors import AgentError
from app.agents.runs import start_agent_run
from app.agents.tools import invoke_tool
from app.models.types import new_id
from app.repositories import inventory as inventory_repo
from app.services.agent_suggestions import create_suggestion, get_suggestion
from app.services.catalog import create_product, create_product_supplier, create_supplier
from app.services.explainer import (
    ExplainerError,
    collect_evidence,
    explanation_is_grounded,
    parse_whatif_query,
    template_explanation,
)
from app.services.exceptions import upsert_open
from app.services.inventory import post_movement
from app.services.replenishment import whatif_compare
from tests.orchestrator.helpers import events_of, owner, run_chat


def _location_id(db, business_id: str) -> str:
    return inventory_repo.list_locations(db, business_id)[0].id


def _product_with_supplier(db, signed, *, sku: str = "OATS-1", name: str = "Oats"):
    supplier = create_supplier(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        name="Mill",
        email="mill@example.com",
        phone=None,
        lead_time_days=4,
    )
    product = create_product(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        sku=sku,
        name=name,
        category_id=None,
        unit="each",
        cost=Decimal("1.00"),
        price=Decimal("2.00"),
        reorder_point=Decimal("10"),
        safety_stock=Decimal("2"),
        preferred_supplier_id=None,
    )
    create_product_supplier(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        product_id=product.id,
        supplier_id=supplier.id,
        unit_cost=Decimal("1.00"),
        lead_time_days=4,
        is_preferred=True,
    )
    post_movement(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        product_id=product.id,
        location_id=_location_id(db, signed.user.business_id),
        movement_type="receipt",
        quantity=Decimal("20"),
        note="Opening",
    )
    return supplier, product


def _sale(db, signed, product_id: str, quantity: str) -> None:
    post_movement(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        product_id=product_id,
        location_id=_location_id(db, signed.user.business_id),
        movement_type="sale",
        quantity=Decimal(quantity),
    )


def _run(db, signed):
    return start_agent_run(
        db,
        business_id=signed.user.business_id,
        agent_name="explainer",
        actor_user_id=signed.user.id,
    )


def _draft_suggestion(db, signed, *, product_id: str, quantity: str = "200"):
    run = _run(db, signed)
    return create_suggestion(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        run_id=run.id,
        suggestion_type="generic",
        payload={
            "title": "Draft 200 units",
            "summary": "Reorder 200 because cover is low.",
            "reason_codes": ["LOW_COVER", "FORECAST_UP"],
            "confidence": "high",
            "evidence": {
                "sku": "OATS-1",
                "product_id": product_id,
                "on_hand": "20",
                "forecast_units": "180",
                "forecast_method": "daily_average",
                "chosen_model": "daily_average",
                "recommended_quantity": quantity,
                "lead_time_days": 4,
                "reliability_score": "1.0",
                "reason_codes": ["LOW_COVER", "FORECAST_UP"],
            },
        },
    )


def test_grounded_why_references_stored_evidence(db) -> None:
    signed = owner(db, "why-ground@example.com", "Why Shop")
    _supplier, product = _product_with_supplier(db, signed)
    suggestion = _draft_suggestion(db, signed, product_id=product.id)
    run = run_chat(db, signed, f"/why suggestion {suggestion['id']}")
    cards = events_of(run, "card")
    assert cards
    card = cards[0].payload["card"]
    assert card["type"] == "explanation"
    assert card["data"]["answerable"] is True
    assert "99999" not in card["message"]
    fields = card["data"]["fields"]
    assert str(fields["recommended_quantity"]) == "200"
    assert "LOW_COVER" in fields["reason_codes"]
    citations = {row["field"]: row["value"] for row in card["data"]["citations"]}
    assert "200" in citations.values()
    assert card["data"]["confidence"]


def test_hallucinated_numbers_trigger_template_fallback(db) -> None:
    signed = owner(db, "why-fake@example.com", "Fake Why Shop")
    _supplier, product = _product_with_supplier(db, signed)
    suggestion = _draft_suggestion(db, signed, product_id=product.id)
    run = run_chat(db, signed, f"/why suggestion {suggestion['id']} invented-why")
    card = events_of(run, "card")[0].payload["card"]
    assert "99999" not in card["message"]
    assert "2099-01-01" not in card["message"]
    assert "200" in card["message"]
    assert card["data"]["used_fallback"] is True


def test_whatif_matches_direct_service(db) -> None:
    signed = owner(db, "whatif@example.com", "Whatif Shop")
    _supplier, product = _product_with_supplier(db, signed)
    _sale(db, signed, product.id, "6")
    direct = whatif_compare(
        db,
        business_id=signed.user.business_id,
        demand_pct=Decimal("20"),
        product_id=product.id,
    )
    run = run_chat(db, signed, f"/whatif demand up 20%")
    card = events_of(run, "card")[0].payload["card"]
    assert card["type"] == "whatif_compare"
    assert card["data"]["answerable"] is True
    items = card["data"]["items"]
    assert items
    match = next(item for item in items if item["product_id"] == product.id)
    expected = next(item for item in direct["items"] if item["product_id"] == product.id)
    assert str(match["after"]["recommended_quantity"]) == str(expected["after"]["recommended_quantity"])
    assert str(match["before"]["recommended_quantity"]) == str(expected["before"]["recommended_quantity"])
    assert match["after"]["stockout_date"] == expected["after"]["stockout_date"]
    assert str(match["after"]["cost"]) == str(expected["after"]["cost"])


def test_unanswerable_why_is_declined(db) -> None:
    signed = owner(db, "why-none@example.com", "Empty Why Shop")
    run = run_chat(db, signed, "/why")
    card = events_of(run, "card")[0].payload["card"]
    assert card["data"]["answerable"] is False
    assert "cannot answer" in card["message"].lower()
    assert card["data"]["missing"]


def test_tenant_isolation_for_suggestion_evidence(db) -> None:
    left = owner(db, "why-a@example.com", "Why A")
    right = owner(db, "why-b@example.com", "Why B")
    _supplier, product = _product_with_supplier(db, left)
    suggestion = _draft_suggestion(db, left, product_id=product.id)
    try:
        get_suggestion(db, business_id=right.user.business_id, suggestion_id=str(suggestion["id"]))
        raise AssertionError("other tenant should not read this suggestion")
    except Exception as exc:
        assert "not found" in str(exc).lower()
    try:
        collect_evidence(
            db,
            business_id=right.user.business_id,
            kind="suggestion",
            target_id=str(suggestion["id"]),
        )
        raise AssertionError("other tenant should not collect this evidence")
    except ExplainerError as exc:
        assert exc.code == "not_found"
    run = start_agent_run(
        db,
        business_id=right.user.business_id,
        agent_name="explainer",
        actor_user_id=right.user.id,
    )
    ctx = AgentContext(
        session=db,
        business_id=right.user.business_id,
        user_id=right.user.id,
        role="owner",
        run_id=run.id,
    )
    try:
        invoke_tool(
            db,
            context=ctx,
            tool_name="get_suggestion",
            arguments={"suggestion_id": str(suggestion["id"])},
            allowlist=frozenset({"get_suggestion"}),
        )
        raise AssertionError("tool should not return another tenant")
    except AgentError as exc:
        assert exc.code == "not_found"


def test_exception_evidence_explains_and_parse_helpers(db) -> None:
    signed = owner(db, "why-ex@example.com", "Why Ex Shop")
    run = _run(db, signed)
    row, _created = upsert_open(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        run_id=run.id,
        exception_type="stockout_risk",
        severity="high",
        entity_type="product",
        entity_id=new_id(),
        dedupe_key=f"stockout_risk:{new_id()}",
        title="OATS-1 is projected to stock out",
        evidence={
            "sku": "OATS-1",
            "on_hand": "2",
            "daily_demand": "1",
            "lead_time_days": 7,
            "days_of_cover": "2",
            "reason_codes": ["stockout_risk"],
            "forecast_method": "daily_average",
        },
        recommended_action="reorder_now",
        rationale="Playbook default.",
        suggestion_id=None,
    )
    packet = collect_evidence(
        db,
        business_id=signed.user.business_id,
        kind="exception",
        target_id=str(row["id"]),
    )
    assert packet["answerable"] is True
    assert packet["fields"]["on_hand"] == "2" or str(packet["fields"]["on_hand"]) == "2"
    grounded = "On-hand is 2 and lead time is 7 days."
    assert explanation_is_grounded(grounded, packet)
    assert not explanation_is_grounded("I invented 99999 units on 2099-01-01.", packet)
    template = template_explanation(packet)
    assert "2" in template
    parsed = parse_whatif_query("supplier delay of 5 days and demand down 10%")
    assert parsed["delay_days"] == 5
    assert parsed["demand_pct"] == Decimal("-10")
    chat = run_chat(db, signed, f"/why exception {row['id']}")
    card = events_of(chat, "card")[0].payload["card"]
    assert card["type"] == "explanation"
    assert card["data"]["answerable"] is True
