from datetime import date
from decimal import Decimal

from app.agents.context import AgentContext
from app.agents.runs import start_agent_run
from app.agents.supplier_comm import SupplierCommAgent
from app.orchestrator.engine import resume_chat_run
from app.repositories import inventory as inventory_repo
from app.services.catalog import create_product, create_product_supplier, create_supplier
from app.services.purchase_orders import create_po
from app.services.team import create_staff_user
from tests.orchestrator.helpers import events_of, owner, run_chat


def test_email_slash_drafts_grounded_numbers(db) -> None:
    signed = owner(db, "comm-owner@example.com", "Comm Shop")
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
    create_product_supplier(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        product_id=product.id,
        supplier_id=supplier.id,
        unit_cost=Decimal("1.50"),
        lead_time_days=4,
        is_preferred=True,
    )
    po = create_po(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        supplier_id=supplier.id,
        expected_date=date(2026, 10, 20),
        location_id=inventory_repo.list_locations(db, signed.user.business_id)[0].id,
        notes=None,
        line_items=[{"product_id": product.id, "quantity": Decimal("12"), "unit_cost": Decimal("1.50")}],
    )
    paused = run_chat(db, signed, "/email Mill chase")
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
    cards = events_of(resumed, "card")
    email = next(item for item in cards if item.payload["card"]["type"] == "email_draft")
    body = str(email.payload["card"]["data"].get("body") or "")
    assert po["po_number"] in body
    assert "12" in body
    assert "2026-10-20" in body
    assert email.payload["card"]["data"].get("console_mode") is True


def test_staff_cannot_draft_email_via_slash(db) -> None:
    signed = owner(db, "comm-staff-owner@example.com", "Staff Comm")
    create_staff_user(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        full_name="Sam Staff",
        email="comm-staff@example.com",
        temporary_password="temp-pass-123",
    )
    from app.services.auth import login

    staff = login(db, email="comm-staff@example.com", password="temp-pass-123")
    run = run_chat(db, staff, "/email Mill chase", role="staff")
    cards = events_of(run, "card")
    assert cards[0].payload["card"]["type"] == "refusal"


def test_compound_email_without_supplier_asks(db) -> None:
    signed = owner(db, "comm-ask@example.com", "Ask Comm")
    run = start_agent_run(
        db,
        business_id=signed.user.business_id,
        agent_name="supplier_comm",
        actor_user_id=signed.user.id,
    )
    agent = SupplierCommAgent()
    agent.attach(
        AgentContext(
            session=db,
            business_id=signed.user.business_id,
            user_id=signed.user.id,
            role="owner",
            run_id=run.id,
        )
    )
    result = agent.typed_result("draft_emails", {}, {}, step_id="s1")
    assert result.status == "ok"
    assert result.data.get("ask_user") is True
