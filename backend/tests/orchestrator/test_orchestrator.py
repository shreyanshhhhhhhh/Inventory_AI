import time

from app.agents.context import AgentContext
from app.agents.runs import start_agent_run
from app.llm.gateway import LLMGateway
from app.llm.providers.fake import FakeProvider
from app.orchestrator.aggregate import summary_is_grounded, write_summary
from app.orchestrator.dispatch import dispatch_plan
from app.orchestrator.engine import cancel_chat_run, resume_chat_run, start_chat_run
from app.orchestrator.registry import AgentSpec, build_default_registry
from app.orchestrator.types import Plan, PlanStep, TypedResult
from app.services.catalog import create_supplier
from app.services.team import create_staff_user
from tests.helpers.tenant import auth_headers, signup_tenant
from tests.orchestrator.helpers import event_types, events_of, owner, run_chat


COMPOUND = "scan for problems, reorder what's needed and draft emails to the suppliers"


def test_compound_request_builds_expected_dag(db) -> None:
    signed = owner(db, "compound@example.com", "Compound Shop")
    run = run_chat(db, signed, COMPOUND)
    assert run.status == "awaiting_approval"
    steps = (run.plan_data or {}).get("steps") or []
    triples = [(item["agent"], item["task"], tuple(item["depends_on"])) for item in steps]
    assert ("exception_monitor", "scan", ()) in triples
    assert ("replenishment", "recommend", ()) in triples
    email = next(item for item in steps if item["task"] == "draft_emails")
    assert set(email["depends_on"]) == {
        next(item["id"] for item in steps if item["task"] == "scan"),
        next(item["id"] for item in steps if item["task"] == "recommend"),
    }
    guard = next(item for item in steps if item["agent"] == "guardrail")
    assert email["id"] in guard["depends_on"]
    assert "awaiting_approval" in event_types(run)


def test_write_plan_runs_after_approval(db) -> None:
    signed = owner(db, "resume@example.com", "Resume Shop")
    run = run_chat(db, signed, COMPOUND)
    assert run.status == "awaiting_approval"
    resumed = resume_chat_run(
        db,
        business_id=signed.user.business_id,
        user_id=signed.user.id,
        run_id=run.id,
        action="run",
        background=False,
    )
    assert resumed.status == "completed"
    assert "done" in event_types(resumed)
    assert "step_done" in event_types(resumed)


def test_invalid_llm_plans_ask_the_user(db) -> None:
    signed = owner(db, "invalid-plan@example.com", "Invalid Plan Shop")
    for marker in (
        "unknown_agent_plan",
        "cycle_plan",
        "too_many_steps_plan",
        "write_before_read_plan",
    ):
        run = run_chat(db, signed, f"Please run a compound job tagged {marker}")
        cards = events_of(run, "card")
        assert cards, marker
        assert cards[0].payload["card"]["type"] == "clarification"
        assert run.status == "completed"


def test_ambiguity_yields_clarification(db) -> None:
    signed = owner(db, "clarify@example.com", "Clarify Shop")
    run = run_chat(db, signed, "maybe stock or maybe forecast I am not sure")
    cards = events_of(run, "card")
    assert cards[0].payload["card"]["type"] == "clarification"
    options = cards[0].payload["card"]["options"]
    assert any("stock" in str(item).lower() or item.get("intent") == "get_stock" for item in options)


def test_out_of_scope_is_refused(db) -> None:
    signed = owner(db, "scope@example.com", "Scope Shop")
    run = run_chat(db, signed, "what is the weather in Paris")
    cards = events_of(run, "card")
    assert cards[0].payload["card"]["type"] == "refusal"
    commands = cards[0].payload["card"]["supported_commands"]
    assert "/forecast" in commands
    assert "/scan" in commands


def test_failed_step_skips_dependents_only(db) -> None:
    signed = owner(db, "skip@example.com", "Skip Shop")
    run = start_agent_run(
        db,
        business_id=signed.user.business_id,
        agent_name="orchestrator",
        actor_user_id=signed.user.id,
    )
    context = AgentContext(
        session=db,
        business_id=signed.user.business_id,
        user_id=signed.user.id,
        role="owner",
        run_id=run.id,
    )
    db.commit()
    plan = Plan(
        [
            PlanStep(
                id="s1",
                agent="exception_monitor",
                task="scan",
                depends_on=[],
                is_write=False,
                params={"_fail": True, "_fail_message": "boom"},
            ),
            PlanStep(
                id="s2",
                agent="replenishment",
                task="recommend",
                depends_on=[],
                is_write=False,
                params={},
            ),
            PlanStep(
                id="s3",
                agent="supplier_comm",
                task="draft_emails",
                depends_on=["s1"],
                is_write=True,
                params={},
            ),
        ]
    )
    results = dispatch_plan(
        plan,
        context=context,
        run_id=run.id,
        timeout_seconds=5,
        retries=0,
        is_cancelled=lambda: False,
    )
    assert results["s1"].status == "failed"
    assert results["s2"].status == "ok"
    assert results["s3"].status == "skipped"


def test_parallel_steps_run_concurrently(db) -> None:
    signed = owner(db, "parallel@example.com", "Parallel Shop")
    run = start_agent_run(
        db,
        business_id=signed.user.business_id,
        agent_name="orchestrator",
        actor_user_id=signed.user.id,
    )
    context = AgentContext(
        session=db,
        business_id=signed.user.business_id,
        user_id=signed.user.id,
        role="owner",
        run_id=run.id,
    )
    db.commit()
    plan = Plan(
        [
            PlanStep(
                id="s1",
                agent="explainer",
                task="explain",
                depends_on=[],
                is_write=False,
                params={"_delay_seconds": 0.3},
            ),
            PlanStep(
                id="s2",
                agent="replenishment",
                task="recommend",
                depends_on=[],
                is_write=False,
                params={"_delay_seconds": 0.3},
            ),
        ]
    )
    started = time.perf_counter()
    results = dispatch_plan(
        plan,
        context=context,
        run_id=run.id,
        timeout_seconds=5,
        retries=0,
        is_cancelled=lambda: False,
    )
    elapsed = time.perf_counter() - started
    assert results["s1"].status == "ok"
    assert results["s2"].status == "ok"
    assert elapsed < 0.55


def test_cancel_works(db) -> None:
    signed = owner(db, "cancel@example.com", "Cancel Shop")
    started = time.time()
    registry = build_default_registry()

    def slow_handler(task, params, inputs, context):
        del task, params, inputs, context
        time.sleep(0.8)
        return TypedResult(
            step_id="s1",
            agent="forecast",
            task="forecast",
            status="not_implemented",
            card_type="forecast_chart",
            message="slow",
        )

    spec = registry.get("forecast")
    assert spec is not None
    registry.register(
        AgentSpec(
            name=spec.name,
            description=spec.description,
            tasks=spec.tasks,
            write_tasks=spec.write_tasks,
            card_type_for_task=spec.card_type_for_task,
            handler=slow_handler,
        )
    )
    run = start_chat_run(
        db,
        business_id=signed.user.business_id,
        user_id=signed.user.id,
        role="owner",
        message="/forecast",
        registry=registry,
        background=True,
    )
    time.sleep(0.15)
    cancelled = cancel_chat_run(
        db,
        business_id=signed.user.business_id,
        user_id=signed.user.id,
        run_id=run.id,
    )
    deadline = time.time() + 3
    while time.time() < deadline:
        db.refresh(cancelled)
        if cancelled.status == "cancelled":
            break
        time.sleep(0.05)
    assert cancelled.status == "cancelled"
    assert time.time() - started < 3


def test_staff_cannot_trigger_owner_only_intents(db) -> None:
    signed = owner(db, "staff-owner@example.com", "Staff Shop")
    staff = create_staff_user(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        full_name="Sam Staff",
        email="staff-orch@example.com",
        temporary_password="staff-pass-123",
    )
    run = start_chat_run(
        db,
        business_id=signed.user.business_id,
        user_id=str(staff["id"]),
        role="staff",
        message="/email",
        gateway=LLMGateway(db),
        background=False,
    )
    cards = events_of(run, "card")
    assert cards[0].payload["card"]["type"] == "refusal"
    assert "owner-only" in cards[0].payload["card"]["message"].lower() or "owner" in cards[0].payload["card"]["message"].lower()


def test_summary_number_check_falls_back_to_template(db) -> None:
    signed = owner(db, "summary@example.com", "Summary Shop")
    results = {
        "s1": TypedResult(
            step_id="s1",
            agent="forecast",
            task="forecast",
            status="not_implemented",
            card_type="forecast_chart",
            data={"implemented": False},
            message="forecast is not implemented yet.",
        )
    }
    assert summary_is_grounded("Placeholder agents reported that they are not implemented yet.", results)
    assert not summary_is_grounded("There are 99999 units at risk.", results)
    provider = FakeProvider(
        {
            "orchestrator_summary": {
                "text": '{"summary":"There are 99999 units at risk."}',
                "tokens_in": 1,
                "tokens_out": 1,
            }
        }
    )
    gateway = LLMGateway(db, provider=provider)
    text = write_summary(
        gateway,
        business_id=signed.user.business_id,
        run_id="run-summary",
        results=results,
    )
    assert "99999" not in text
    assert "Finished 1 steps" in text


def test_tenant_cannot_access_another_business_run(client, db) -> None:
    first = signup_tenant(client, email="orch-a@example.com", business_name="Shop A")
    second = signup_tenant(client, email="orch-b@example.com", business_name="Shop B")
    created = client.post(
        "/api/v1/chat/runs",
        headers=auth_headers(first.access_token),
        json={"message": "/forecast"},
    )
    assert created.status_code == 202, created.text
    run_id = created.json()["id"]
    denied = client.get(
        f"/api/v1/chat/runs/{run_id}/events",
        headers=auth_headers(second.access_token),
    )
    assert denied.status_code == 404
    denied_detail = client.get(
        f"/api/v1/chat/runs/{run_id}",
        headers=auth_headers(second.access_token),
    )
    assert denied_detail.status_code == 404
    own = client.get(
        f"/api/v1/chat/runs/{run_id}",
        headers=auth_headers(first.access_token),
    )
    assert own.status_code == 200
    body = own.json()
    assert body["id"] == run_id
    assert isinstance(body["events"], list)
    also = client.post(
        f"/api/v1/chat/runs/{run_id}/cancel",
        headers=auth_headers(second.access_token),
    )
    assert also.status_code == 404


def test_history_resolves_supplier_name_in_code(db) -> None:
    signed = owner(db, "acme@example.com", "Acme Shop")
    supplier = create_supplier(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        name="Acme",
        email="acme@example.com",
        phone=None,
        lead_time_days=7,
    )
    first = run_chat(db, signed, "Talking about Acme the supplier")
    assert first.status in {"completed", "awaiting_approval"}
    run = run_chat(db, signed, "do it for that supplier")
    assert run.status == "awaiting_approval"
    steps = (run.plan_data or {}).get("steps") or []
    email = next(item for item in steps if item["task"] == "draft_emails")
    assert email["params"].get("supplier_id") == supplier.id
