from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.agents.context import AgentContext
from app.orchestrator.types import TypedResult


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
    del params, context
    return TypedResult(
        step_id="guardrail",
        agent="guardrail",
        task=task,
        status="ok",
        card_type="text",
        data={"approved_inputs": list(inputs)},
        message="Write steps passed the plan guardrail.",
    )


def build_default_registry() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(
        _placeholder(
            "forecast",
            tasks=frozenset({"forecast", "get_stock"}),
            write_tasks=frozenset(),
            cards={"forecast": "forecast_chart", "get_stock": "stock_table"},
            description="Demand forecast and on-hand stock reads.",
        )
    )
    registry.register(
        _placeholder(
            "exception_monitor",
            tasks=frozenset({"scan"}),
            write_tasks=frozenset(),
            cards={"scan": "exception_list"},
            description="Stockout, overdue PO, and receive-mismatch scans.",
        )
    )
    registry.register(
        _placeholder(
            "replenishment",
            tasks=frozenset({"recommend", "draft_po"}),
            write_tasks=frozenset({"draft_po"}),
            cards={"recommend": "text", "draft_po": "po_suggestion"},
            description="Reorder quantities and draft purchase-order suggestions.",
        )
    )
    registry.register(
        _placeholder(
            "supplier_comm",
            tasks=frozenset({"draft_emails"}),
            write_tasks=frozenset({"draft_emails"}),
            cards={"draft_emails": "email_draft"},
            description="Draft supplier emails. Does not send mail.",
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
            description="Plan-level write gate. Records that a human approved the DAG.",
            tasks=frozenset({"review"}),
            write_tasks=frozenset(),
            card_type_for_task={"review": "text"},
            handler=_guardrail_handler,
        )
    )
    return registry


DEFAULT_REGISTRY = build_default_registry()
