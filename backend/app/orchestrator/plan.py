from __future__ import annotations

from app.orchestrator.errors import OrchestratorError
from app.orchestrator.registry import AgentRegistry, DEFAULT_REGISTRY
from app.orchestrator.types import Plan, PlanStep, ProposedPlan

GUARDRAIL_ID = "guardrail"
GUARDRAIL_AGENT = "guardrail"
GUARDRAIL_TASK = "review"

# Single known intents. Compound requests go through the LLM, then this table's
# agent/task names are the only ones CODE will accept.
ROUTING_TABLE: dict[str, list[tuple[str, str, str, list[str]]]] = {
    # id, agent, task, depends_on
    "get_stock": [("s1", "forecast", "get_stock", [])],
    "forecast": [("s1", "forecast", "forecast", [])],
    "scan_exceptions": [("s1", "exception_monitor", "scan", [])],
    "reorder": [("s1", "replenishment", "recommend", [])],
    "draft_po": [
        ("s1", "replenishment", "recommend", []),
        ("s2", "replenishment", "draft_po", ["s1"]),
    ],
    "draft_email": [
        ("s1", "replenishment", "recommend", []),
        ("s2", "supplier_comm", "draft_emails", ["s1"]),
    ],
    "explain": [("s1", "explainer", "explain", [])],
    "data_quality": [("s1", "data_quality", "check", [])],
}


class PlanValidationError(OrchestratorError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail, code="invalid_plan", status_code=400)


def plan_from_intents(
    intents: list[tuple[str, dict[str, object]]],
    *,
    registry: AgentRegistry | None = None,
) -> Plan | None:
    if len(intents) != 1:
        return None
    intent, params = intents[0]
    rows = ROUTING_TABLE.get(intent)
    if rows is None:
        return None
    book = registry or DEFAULT_REGISTRY
    steps = [
        PlanStep(
            id=step_id,
            agent=agent,
            task=task,
            depends_on=list(depends_on),
            is_write=book.is_write(agent, task),
            intent=intent,
            params=dict(params),
        )
        for step_id, agent, task, depends_on in rows
    ]
    return attach_guardrail(Plan(steps), registry=book)


def attach_guardrail(plan: Plan, *, registry: AgentRegistry | None = None) -> Plan:
    book = registry or DEFAULT_REGISTRY
    writes = [step for step in plan.steps if book.is_write(step.agent, step.task)]
    existing = [step for step in plan.steps if step.agent == GUARDRAIL_AGENT]
    if not writes:
        return plan
    if existing:
        return plan
    guard = PlanStep(
        id=GUARDRAIL_ID,
        agent=GUARDRAIL_AGENT,
        task=GUARDRAIL_TASK,
        depends_on=[step.id for step in writes],
        is_write=False,
        intent=None,
        params={},
    )
    return Plan([*plan.steps, guard])


def proposed_to_plan(
    proposed: ProposedPlan,
    *,
    intent_params: dict[str, dict[str, object]] | None = None,
    registry: AgentRegistry | None = None,
) -> Plan:
    book = registry or DEFAULT_REGISTRY
    params_by_agent_task = intent_params or {}
    steps: list[PlanStep] = []
    for item in proposed.steps:
        key = f"{item.agent}.{item.task}"
        steps.append(
            PlanStep(
                id=item.id,
                agent=item.agent,
                task=item.task,
                depends_on=list(item.depends_on),
                is_write=book.is_write(item.agent, item.task),
                params=dict(params_by_agent_task.get(key) or {}),
            )
        )
    return attach_guardrail(Plan(steps), registry=book)


def validate_plan(
    plan: Plan,
    *,
    max_steps: int,
    registry: AgentRegistry | None = None,
) -> None:
    book = registry or DEFAULT_REGISTRY
    if not plan.steps:
        raise PlanValidationError("The plan has no steps.")
    if len(plan.steps) > max_steps:
        raise PlanValidationError(f"The plan has more than {max_steps} steps.")
    ids = [step.id for step in plan.steps]
    if len(ids) != len(set(ids)):
        raise PlanValidationError("The plan has duplicate step ids.")
    by_id = plan.by_id()
    for step in plan.steps:
        if step.agent != GUARDRAIL_AGENT and not book.has_task(step.agent, step.task):
            raise PlanValidationError(f"Unknown agent or task: {step.agent}.{step.task}.")
        if step.agent == GUARDRAIL_AGENT and step.task != GUARDRAIL_TASK:
            raise PlanValidationError("Guardrail task must be review.")
        if not _valid_id(step.id):
            raise PlanValidationError(f"Invalid step id '{step.id}'.")
        for dep in step.depends_on:
            if dep not in by_id:
                raise PlanValidationError(f"Step {step.id} depends on unknown step {dep}.")
    if _has_cycle(plan):
        raise PlanValidationError("The plan has a cycle.")
    for step in plan.steps:
        if step.agent == GUARDRAIL_AGENT:
            continue
        write_step = book.is_write(step.agent, step.task)
        for dep_id in step.depends_on:
            dep = by_id[dep_id]
            write_dep = book.is_write(dep.agent, dep.task)
            if write_dep and not write_step:
                raise PlanValidationError("Write steps must come after the read steps they depend on.")
            if write_step and dep.agent == GUARDRAIL_AGENT:
                raise PlanValidationError("Write steps must come after the read steps they depend on.")
    writes = [step for step in plan.steps if book.is_write(step.agent, step.task)]
    if writes:
        guards = [step for step in plan.steps if step.agent == GUARDRAIL_AGENT]
        if not guards:
            raise PlanValidationError("Every write step must end in the guardrail.")
        for write in writes:
            if not any(write.id in _ancestors(plan, guard.id) for guard in guards):
                raise PlanValidationError("Every write step must end in the guardrail.")


def _valid_id(value: str) -> bool:
    return bool(value) and value.replace("_", "").replace("-", "").isalnum()


def _has_cycle(plan: Plan) -> bool:
    visiting: set[str] = set()
    seen: set[str] = set()
    by_id = plan.by_id()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in seen:
            return False
        visiting.add(node)
        for dep in by_id[node].depends_on:
            if visit(dep):
                return True
        visiting.remove(node)
        seen.add(node)
        return False

    return any(visit(step.id) for step in plan.steps)


def _ancestors(plan: Plan, step_id: str) -> set[str]:
    by_id = plan.by_id()
    found: set[str] = set()
    stack = list(by_id[step_id].depends_on)
    while stack:
        current = stack.pop()
        if current in found:
            continue
        found.add(current)
        stack.extend(by_id[current].depends_on)
    return found
