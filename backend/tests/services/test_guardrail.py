import ast
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select

from app.agents.context import AgentContext
from app.agents.errors import AgentError
from app.agents.runs import start_agent_run
from app.agents.tools import invoke_tool
from app.models import PurchaseOrder
from app.repositories.businesses import get_business
from app.services.agent_suggestions import (
    AgentSuggestionError,
    approve_suggestion,
    create_guarded_po_suggestion,
    create_suggestion,
    list_suggestions,
    reject_suggestion,
)
from app.services.auth import signup
from app.services.catalog import (
    archive_supplier,
    create_product,
    create_product_supplier,
    create_supplier,
)
from app.services.guardrail import PoLineProposal, PoProposal, validate_po_proposal
from app.services.inventory import post_movement
from app.services.purchase_orders import create_po
from app.services.settings import update_autonomy_rules
from app.repositories import inventory as inventory_repo
from app.services.team import create_staff_user


def _owner(db, email: str, shop: str):
    return signup(
        db,
        full_name="Ada Owner",
        email=email,
        password="correct-horse-1",
        business_name=shop,
    )


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


def _seed(db, email: str):
    owner = _owner(db, email, "Guard Shop")
    business_id = owner.user.business_id
    supplier = create_supplier(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        name="Mill",
        email="mill@example.com",
        phone=None,
        lead_time_days=4,
    )
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
    create_product_supplier(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product.id,
        supplier_id=supplier.id,
        unit_cost=Decimal("1.00"),
        lead_time_days=4,
        is_preferred=True,
    )
    post_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product.id,
        location_id=_location_id(db, business_id),
        movement_type="receipt",
        quantity=Decimal("3"),
        note="Opening",
    )
    return owner, supplier, product


def _proposal(supplier_id: str, product_id: str, *, quantity: str = "9", unit_cost: str = "1.00") -> PoProposal:
    return PoProposal(
        supplier_id=supplier_id,
        lines=(
            PoLineProposal(
                product_id=product_id,
                quantity=Decimal(quantity),
                unit_cost=Decimal(unit_cost),
            ),
        ),
    )


def _run(db, owner):
    return start_agent_run(
        db,
        business_id=owner.user.business_id,
        agent_name="replenishment",
        actor_user_id=owner.user.id,
    )


def test_guardrail_rejects_bad_sku_huge_quantity_and_price_mismatch(db) -> None:
    owner, supplier, product = _seed(db, "guard-bad@example.com")
    business = get_business(db, owner.user.business_id)
    assert business is not None

    bad_sku = validate_po_proposal(
        _proposal(supplier.id, str(uuid4())),
        business,
        session=db,
    )
    assert bad_sku.passed is False
    assert "unknown_sku" in bad_sku.reasons
    assert bad_sku.required_approval == "human"

    huge = validate_po_proposal(
        _proposal(supplier.id, product.id, quantity="5000"),
        business,
        session=db,
    )
    assert huge.passed is False
    assert "quantity_exceeds_line_limit" in huge.reasons

    mismatch = validate_po_proposal(
        _proposal(supplier.id, product.id, unit_cost="9.00"),
        business,
        session=db,
    )
    assert mismatch.passed is False
    assert "cost_mismatch" in mismatch.reasons

    fractional = validate_po_proposal(
        _proposal(supplier.id, product.id, quantity="2.5"),
        business,
        session=db,
    )
    assert "quantity_not_integer" in fractional.reasons
    whole = validate_po_proposal(
        _proposal(supplier.id, product.id, quantity="2.0000"),
        business,
        session=db,
    )
    assert whole.passed is True


def test_guardrail_rejects_duplicate_open_po_and_inactive_supplier(db) -> None:
    owner, supplier, product = _seed(db, "guard-dup@example.com")
    business = get_business(db, owner.user.business_id)
    assert business is not None
    create_po(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        supplier_id=supplier.id,
        expected_date=None,
        location_id=None,
        notes=None,
        line_items=[{"product_id": product.id, "quantity": "9", "unit_cost": "1.00"}],
    )
    duplicate = validate_po_proposal(
        _proposal(supplier.id, product.id),
        business,
        session=db,
    )
    assert duplicate.passed is False
    assert "duplicate_open_po" in duplicate.reasons
    before = _po_count(db, owner.user.business_id)
    run = _run(db, owner)
    try:
        create_guarded_po_suggestion(
            db,
            business_id=owner.user.business_id,
            actor_user_id=owner.user.id,
            actor_role="owner",
            run_id=run.id,
            payload={
                "supplier_id": supplier.id,
                "lines": [{"product_id": product.id, "quantity": "9", "unit_cost": "1.00"}],
                "title": "Dup",
                "summary": "Dup",
            },
        )
    except AgentSuggestionError as exc:
        assert exc.code == "guardrail_rejected"
        assert "duplicate_open_po" in exc.message
    else:
        raise AssertionError("duplicate proposal was stored")
    assert list_suggestions(db, business_id=owner.user.business_id) == []
    assert _po_count(db, owner.user.business_id) == before

    archive_supplier(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        supplier_id=supplier.id,
    )
    inactive = validate_po_proposal(
        PoProposal(
            supplier_id=supplier.id,
            lines=(
                PoLineProposal(
                    product_id=product.id,
                    quantity=Decimal("1"),
                    unit_cost=Decimal("1.00"),
                ),
            ),
        ),
        business,
        session=db,
    )
    assert "inactive_supplier" in inactive.reasons


def test_auto_approve_threshold_and_human_default(db) -> None:
    owner, supplier, product = _seed(db, "guard-auto@example.com")
    business_id = owner.user.business_id
    run = _run(db, owner)
    payload = {
        "supplier_id": supplier.id,
        "lines": [{"product_id": product.id, "quantity": "9", "unit_cost": "1.00"}],
        "title": "Oats",
        "summary": "Oats",
        "reason_codes": ["LOW_COVER"],
        "confidence": "0.90",
    }
    pending = create_guarded_po_suggestion(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        actor_role="owner",
        run_id=run.id,
        payload=payload,
    )
    assert pending["status"] == "pending"
    assert _po_count(db, business_id) == 0
    assert pending["payload"]["guardrail"]["required_approval"] == "human"

    update_autonomy_rules(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        auto_approve_below_amount=Decimal("1"),
    )
    run_low = _run(db, owner)
    still_human = create_guarded_po_suggestion(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        actor_role="owner",
        run_id=run_low.id,
        payload=payload,
    )
    assert still_human["status"] == "pending"
    assert _po_count(db, business_id) == 0

    update_autonomy_rules(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        auto_approve_below_amount=Decimal("100"),
    )
    run_auto = _run(db, owner)
    auto = create_guarded_po_suggestion(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        actor_role="owner",
        run_id=run_auto.id,
        payload=payload,
    )
    assert auto["status"] == "approved"
    assert auto["payload"]["decisions"][0]["action"] == "auto_approved"
    po = db.get(PurchaseOrder, auto["payload"]["purchase_order_id"])
    assert po is not None
    assert po.status == "draft"
    assert po.business_id == business_id


def test_reject_leaves_no_po_and_keeps_the_reason(db) -> None:
    owner, supplier, product = _seed(db, "guard-reject@example.com")
    run = _run(db, owner)
    created = create_guarded_po_suggestion(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        actor_role="owner",
        run_id=run.id,
        payload={
            "supplier_id": supplier.id,
            "lines": [{"product_id": product.id, "quantity": "9", "unit_cost": "1.00"}],
            "title": "Oats",
            "summary": "Oats",
        },
    )
    rejected = reject_suggestion(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        actor_role="owner",
        suggestion_id=str(created["id"]),
        reason="Price moved.",
    )
    assert rejected["status"] == "rejected"
    assert rejected["payload"]["decisions"][0]["action"] == "rejected"
    assert rejected["payload"]["decisions"][0]["reason"] == "Price moved."
    assert _po_count(db, owner.user.business_id) == 0


def test_owner_approval_creates_a_draft_po_and_staff_cannot(db) -> None:
    owner, supplier, product = _seed(db, "guard-owner@example.com")
    other = _owner(db, "guard-other@example.com", "Other Shop")
    staff = create_staff_user(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        full_name="Sam Staff",
        email="guard-staff@example.com",
        temporary_password="staff-pass-123",
    )
    run = _run(db, owner)
    created = create_guarded_po_suggestion(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        actor_role="owner",
        run_id=run.id,
        payload={
            "supplier_id": supplier.id,
            "lines": [{"product_id": product.id, "quantity": "9", "unit_cost": "1.00"}],
            "title": "Oats",
            "summary": "Oats",
        },
    )
    try:
        approve_suggestion(
            db,
            business_id=owner.user.business_id,
            actor_user_id=str(staff["id"]),
            actor_role="staff",
            suggestion_id=str(created["id"]),
        )
    except AgentSuggestionError as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("staff approved a purchase suggestion")
    assert _po_count(db, owner.user.business_id) == 0

    try:
        approve_suggestion(
            db,
            business_id=other.user.business_id,
            actor_user_id=other.user.id,
            actor_role="owner",
            suggestion_id=str(created["id"]),
        )
    except AgentSuggestionError as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("other tenant approved the suggestion")

    approved = approve_suggestion(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        actor_role="owner",
        suggestion_id=str(created["id"]),
    )
    assert approved["status"] == "approved"
    assert approved["payload"]["decisions"][-1]["action"] == "approved"
    po = db.get(PurchaseOrder, approved["payload"]["purchase_order_id"])
    assert po is not None
    assert po.status == "draft"
    assert po.business_id == owner.user.business_id


def test_draft_po_suggestion_without_guardrail_is_rejected(db) -> None:
    owner, supplier, product = _seed(db, "guard-gate@example.com")
    run = _run(db, owner)
    try:
        create_suggestion(
            db,
            business_id=owner.user.business_id,
            actor_user_id=owner.user.id,
            run_id=run.id,
            suggestion_type="draft_po",
            payload={"supplier_id": supplier.id, "lines": []},
        )
    except AgentSuggestionError as exc:
        assert exc.code == "guardrail_required"
    else:
        raise AssertionError("ungated draft_po suggestion was stored")
    assert list_suggestions(db, business_id=owner.user.business_id) == []

    context = AgentContext(
        session=db,
        business_id=owner.user.business_id,
        user_id=owner.user.id,
        role="owner",
        run_id=run.id,
    )
    try:
        invoke_tool(
            db,
            context=context,
            tool_name="create_draft_po_suggestion",
            arguments={
                "supplier_id": supplier.id,
                "lines": [{"product_id": str(uuid4()), "quantity": "9", "unit_cost": "1.00"}],
            },
            allowlist=frozenset({"create_draft_po_suggestion"}),
        )
    except AgentError as exc:
        assert exc.code == "guardrail_rejected"
    else:
        raise AssertionError("bad SKU suggestion was stored")
    assert list_suggestions(db, business_id=owner.user.business_id) == []
    assert _po_count(db, owner.user.business_id) == 0
    del product


def test_no_agent_path_creates_a_po_or_draft_suggestion_without_the_guardrail() -> None:
    root = Path(__file__).resolve().parents[2] / "app"
    allowed_create_po = {
        "routers/purchase_orders.py",
        "services/demo_seed.py",
        "services/agent_suggestions.py",
    }
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name == "create_po":
                assert rel in allowed_create_po, rel
            if name != "create_suggestion":
                continue
            for keyword in node.keywords:
                if (
                    keyword.arg == "suggestion_type"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value == "draft_po"
                ):
                    assert rel == "services/agent_suggestions.py"

    source = (root / "services" / "agent_suggestions.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    approve = _function(module, "approve_suggestion")
    guarded = _function(module, "create_guarded_po_suggestion")
    assert _first_call_line(approve, "validate_po_proposal") < _first_call_line(approve, "create_po")
    assert _first_call_line(guarded, "validate_po_proposal") < _first_call_line(
        guarded, "create_suggestion"
    )
    assert _first_call_line(guarded, "po_write_gate") < _first_call_line(guarded, "create_suggestion")
    agent_root = root / "agents"
    orchestrator_root = root / "orchestrator"
    for folder in (agent_root, orchestrator_root):
        for path in folder.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _call_name(node) == "create_po":
                    raise AssertionError(path.relative_to(root).as_posix())


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _function(module: ast.AST, name: str) -> ast.FunctionDef:
    for node in module.body:  # type: ignore[attr-defined]
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(name)


def _first_call_line(function: ast.FunctionDef, name: str) -> int:
    lines = [
        node.lineno
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and _call_name(node) == name
    ]
    assert lines, name
    return min(lines)
