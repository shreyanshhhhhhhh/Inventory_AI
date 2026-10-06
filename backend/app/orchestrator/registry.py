from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.agents.context import AgentContext
from app.agents.exception_monitor import exception_monitor_handler
from app.agents.forecast import forecast_agent_handler
from app.agents.replenishment import replenishment_handler
from app.agents.supplier_comm import supplier_comm_handler
from app.orchestrator.types import TypedResult
from app.repositories.businesses import get_business
from app.services.guardrail import proposal_from_mapping, validate_po_proposal


@dataclass(frozen=True)
class AgentSpec:
    name: str
    description: str
    tasks: frozenset[str]
    write_tasks: frozenset[str]
    card_type_for_task: dict[str, str]
    handler: Callable[[str, dict[str, Any], dict[str, TypedResult], AgentContext], TypedResult]


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentSpec] = {}

    def register(self, spec: AgentSpec) -> None:
        self._agents[spec.name] = spec

    def get(self, name: str) -> AgentSpec | None:
        return self._agents.get(name)

    def names(self) -> frozenset[str]:
        return frozenset(self._agents)

    def has_task(self, agent: str, task: str) -> bool:
        spec = self._agents.get(agent)
        return spec is not None and task in spec.tasks

    def is_write(self, agent: str, task: str) -> bool:
        spec = self._agents.get(agent)
        if spec is None:
            return False
        return task in spec.write_tasks

    def run_task(
        self,
        *,
        agent: str,
        task: str,
        params: dict[str, Any],
        inputs: dict[str, TypedResult],
        context: AgentContext,
        step_id: str,
    ) -> TypedResult:
        spec = self._agents.get(agent)
        if spec is None or task not in spec.tasks:
            return TypedResult(
                step_id=step_id,
                agent=agent,
                task=task,
                status="failed",
                card_type="text",
                message=f"Unknown agent or task: {agent}.{task}",
            )
        return spec.handler(task, params, inputs, context)


def _placeholder(
    name: str,
    *,
    tasks: frozenset[str],
    write_tasks: frozenset[str],
    cards: dict[str, str],
    description: str,
) -> AgentSpec:
    def handler(
        task: str,
        params: dict[str, Any],
        inputs: dict[str, TypedResult],
        context: AgentContext,
    ) -> TypedResult:
        del context
        delay = params.get("_delay_seconds")
        if delay:
            import time

            time.sleep(float(delay))
        if params.get("_fail"):
            raise RuntimeError(str(params.get("_fail_message") or f"{name}.{task} failed"))
        card = cards.get(task, "text")
        return TypedResult(
            step_id=str(params.get("_step_id") or task),
            agent=name,
            task=task,
            status="not_implemented",
            card_type=card,  # type: ignore[arg-type]
            data={
                "implemented": False,
                "params": {key: value for key, value in params.items() if not key.startswith("_")},
                "input_step_ids": list(inputs),
            },
            message=f"{name} is not implemented yet.",
        )

    return AgentSpec(
        name=name,
        description=description,
        tasks=tasks,
        write_tasks=write_tasks,
        card_type_for_task=cards,
        handler=handler,
    )


def _guardrail_handler(
    task: str,
    params: dict[str, Any],
    inputs: dict[str, TypedResult],
    context: AgentContext,
) -> TypedResult:
    step_id = str(params.get("_step_id") or "guardrail")
    business = get_business(context.session, context.business_id)
    checks: list[dict[str, object]] = []
    failures: list[str] = []
    if business is not None:
        for result in inputs.values():
            raw_proposals = result.data.get("proposals") if isinstance(result.data, dict) else None
            if not isinstance(raw_proposals, list):
                continue
            for raw in raw_proposals:
                proposal = proposal_from_mapping(raw)
                if proposal is None:
                    failures.append("malformed_proposal")
                    continue
                outcome = validate_po_proposal(proposal, business, session=context.session)
                checks.append(outcome.to_dict())
                if not outcome.passed:
                    failures.extend(outcome.reasons)
    if failures:
        return TypedResult(
            step_id=step_id,
            agent="guardrail",
            task=task,
            status="failed",
            card_type="text",
            data={"reasons": failures, "checks": checks, "approved_inputs": list(inputs)},
            message="Guardrail rejected the purchase proposal.",
        )
    message = (
        "Purchase proposal passed the guardrail."
        if checks
        else "Write steps passed the plan guardrail."
    )
    return TypedResult(
        step_id=step_id,
        agent="guardrail",
        task=task,
        status="ok",
        card_type="text",
        data={"checks": checks, "approved_inputs": list(inputs)},
        message=message,
    )


def build_default_registry() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(
        AgentSpec(
            name="forecast",
            description="Demand forecast and on-hand stock reads.",
            tasks=frozenset({"forecast", "get_stock"}),
            write_tasks=frozenset(),
            card_type_for_task={"forecast": "forecast_chart", "get_stock": "stock_table"},
            handler=forecast_agent_handler,
        )
    )
    registry.register(
        AgentSpec(
            name="exception_monitor",
            description="Deterministic exception scan with playbook-ranked suggestions.",
            tasks=frozenset({"scan"}),
            write_tasks=frozenset(),
            card_type_for_task={"scan": "exception_list"},
            handler=exception_monitor_handler,
        )
    )
    registry.register(
        AgentSpec(
            name="replenishment",
            description="Reorder recommendations and guarded purchase-order suggestions.",
            tasks=frozenset({"recommend", "draft_po"}),
            write_tasks=frozenset({"draft_po"}),
            card_type_for_task={"recommend": "text", "draft_po": "po_suggestion"},
            handler=replenishment_handler,
        )
    )
    registry.register(
        AgentSpec(
            name="supplier_comm",
            description="Draft supplier emails from order facts. Does not send mail.",
            tasks=frozenset({"draft_emails"}),
            write_tasks=frozenset({"draft_emails"}),
            card_type_for_task={"draft_emails": "email_draft"},
            handler=supplier_comm_handler,
        )
    )
    registry.register(
        _placeholder(
            "explainer",
            tasks=frozenset({"explain"}),
            write_tasks=frozenset(),
            cards={"explain": "text"},
            description="Plain-language explanations of inventory figures.",
        )
    )
    registry.register(
        _placeholder(
            "data_quality",
            tasks=frozenset({"check"}),
            write_tasks=frozenset(),
            cards={"check": "text"},
            description="Catalog and ledger data-quality checks.",
        )
    )
    registry.register(
        AgentSpec(
            name="guardrail",
            description="Re-checks purchase proposals after plan approval. Does not create purchase orders.",
            tasks=frozenset({"review"}),
            write_tasks=frozenset(),
            card_type_for_task={"review": "text"},
            handler=_guardrail_handler,
        )
    )
    return registry


DEFAULT_REGISTRY = build_default_registry()
