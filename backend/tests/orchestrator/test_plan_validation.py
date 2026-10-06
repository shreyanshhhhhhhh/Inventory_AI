from app.orchestrator.plan import PlanValidationError, proposed_to_plan, validate_plan
from app.orchestrator.types import ProposedPlan, PlanStepModel


def _plan(steps: list[dict]) -> None:
    proposed = ProposedPlan(steps=[PlanStepModel.model_validate(item) for item in steps])
    plan = proposed_to_plan(proposed)
    validate_plan(plan, max_steps=12)


def test_unknown_agent_is_rejected() -> None:
    try:
        _plan([{"id": "s1", "agent": "unknown_agent", "task": "scan", "depends_on": []}])
    except PlanValidationError as exc:
        assert "Unknown agent" in exc.detail
        return
    raise AssertionError("expected PlanValidationError")


def test_cycle_is_rejected() -> None:
    try:
        _plan(
            [
                {"id": "s1", "agent": "exception_monitor", "task": "scan", "depends_on": ["s2"]},
                {"id": "s2", "agent": "replenishment", "task": "recommend", "depends_on": ["s1"]},
            ]
        )
    except PlanValidationError as exc:
        assert "cycle" in exc.detail
        return
    raise AssertionError("expected PlanValidationError")


def test_too_many_steps_is_rejected() -> None:
    steps = [
        {"id": f"s{index}", "agent": "forecast", "task": "forecast", "depends_on": []}
        for index in range(1, 14)
    ]
    try:
        _plan(steps)
    except PlanValidationError as exc:
        assert "more than" in exc.detail
        return
    raise AssertionError("expected PlanValidationError")


def test_write_before_read_is_rejected() -> None:
    try:
        _plan(
            [
                {"id": "s1", "agent": "supplier_comm", "task": "draft_emails", "depends_on": []},
                {"id": "s2", "agent": "replenishment", "task": "recommend", "depends_on": ["s1"]},
            ]
        )
    except PlanValidationError as exc:
        assert "Write steps" in exc.detail
        return
    raise AssertionError("expected PlanValidationError")
