from __future__ import annotations

from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.context import AgentContext
from app.core.config import settings
from app.llm.gateway import LLMGateway
from app.llm.prompts.registry import get_prompt
from app.llm.providers.base import ChatMessage
from app.llm.security import DATA_BLOCK_INSTRUCTIONS, wrap_untrusted
from app.orchestrator.aggregate import template_summary, write_summary
from app.orchestrator.dispatch import dispatch_plan
from app.orchestrator.events import BUS, OrchestratorEvent
from app.orchestrator.plan import (
    PlanValidationError,
    plan_from_intents,
    proposed_to_plan,
    validate_plan,
)
from app.orchestrator.registry import AgentRegistry, DEFAULT_REGISTRY
from app.orchestrator.types import Plan, ProposedPlan, TypedResult
from app.orchestrator.understand import understand_message


class OrchestratorState(TypedDict, total=False):
    run_id: str
    message: str
    history: list[dict[str, str]]
    role: str
    business_id: str
    user_id: str
    resume_from: str
    approved: bool
    edited_plan: dict[str, Any] | None
    outcome: str
    intents: list[dict[str, Any]]
    confidence: float
    understand_card: dict[str, Any] | None
    plan: dict[str, Any]
    needs_approval: bool
    results: dict[str, Any]
    cards: list[dict[str, Any]]
    summary: str
    reply: str


class OrchestratorRuntime:
    def __init__(
        self,
        session: Session,
        *,
        gateway: LLMGateway,
        registry: AgentRegistry | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        emit: Callable[[OrchestratorEvent], None] | None = None,
    ) -> None:
        self.session = session
        self.gateway = gateway
        self.registry = registry or DEFAULT_REGISTRY
        self.is_cancelled = is_cancelled or (lambda: False)
        self.emit = emit or BUS.emit

    def _thinking(self, run_id: str, message: str) -> None:
        self.emit(OrchestratorEvent(type="thinking", run_id=run_id, payload={"message": message}))

    def understand(self, state: OrchestratorState, _config: object | None = None) -> OrchestratorState:
        self._thinking(state["run_id"], "Understanding your request.")
        result = understand_message(
            self.session,
            gateway=self.gateway,
            business_id=state["business_id"],
            run_id=state["run_id"],
            message=state["message"],
            history=list(state.get("history") or []),
            role=state["role"],
        )
        return {
            "outcome": str(result["outcome"]),
            "intents": list(result.get("intents") or []),
            "confidence": float(result.get("confidence") or 0),
            "understand_card": result.get("card"),
        }

    def validate(self, state: OrchestratorState, _config: object | None = None) -> OrchestratorState:
        self._thinking(state["run_id"], "Checking what I can do for this shop and role.")
        return {}

    def plan(self, state: OrchestratorState, _config: object | None = None) -> OrchestratorState:
        self._thinking(state["run_id"], "Building a plan.")
        intents = [(str(item["intent"]), dict(item.get("params") or {})) for item in state.get("intents") or []]
        built = plan_from_intents(intents, registry=self.registry)
        if built is None:
            built = self._llm_plan(state, intents)
        if built is None:
            return {
                "outcome": "clarify",
                "understand_card": {
                    "type": "clarification",
                    "message": "I could not build a valid plan. Tell me which steps to run.",
                    "options": [{"intent": item[0], "label": item[0]} for item in intents],
                },
            }
        try:
            validate_plan(built, max_steps=settings.orchestrator_max_steps, registry=self.registry)
        except PlanValidationError:
            return {
                "outcome": "clarify",
                "understand_card": {
                    "type": "clarification",
                    "message": "The plan was invalid after a retry. Tell me which steps to run.",
                    "options": [{"intent": item[0], "label": item[0]} for item in intents],
                },
            }
        self.emit(
            OrchestratorEvent(
                type="plan",
                run_id=state["run_id"],
                payload=built.to_dict(),
            )
        )
        return {"plan": built.to_dict(), "needs_approval": built.has_writes, "outcome": "ok"}

    def _llm_plan(self, state: OrchestratorState, intents: list[tuple[str, dict[str, object]]]) -> Plan | None:
        prompt = get_prompt("compound_plan")
        payload = {
            "intents": [{"intent": name, "params": params} for name, params in intents],
            "registered_agents": sorted(self.registry.names()),
        }
        messages = [
            ChatMessage(role="system", content=f"{prompt.template}\n{DATA_BLOCK_INSTRUCTIONS}"),
            ChatMessage(role="user", content=wrap_untrusted(payload, label="intents")),
        ]
        last_error = ""
        for attempt in range(2):
            working = list(messages)
            if last_error:
                working.append(
                    ChatMessage(
                        role="user",
                        content=wrap_untrusted({"validation_error": last_error}, label="plan_error"),
                    )
                )
            try:
                proposed = self.gateway.complete_structured(
                    working,
                    ProposedPlan,
                    prompt_name="compound_plan",
                    business_id=state["business_id"],
                    run_id=state["run_id"],
                )
                merged: dict[str, object] = {}
                for _name, params in intents:
                    merged.update(params)
                intent_params = {
                    f"{item.agent}.{item.task}": dict(merged) for item in proposed.steps
                }
                plan = proposed_to_plan(proposed, intent_params=intent_params, registry=self.registry)
                validate_plan(plan, max_steps=settings.orchestrator_max_steps, registry=self.registry)
                return plan
            except (PlanValidationError, Exception) as exc:
                last_error = str(exc)
                continue
        return None

    def approve_plan(self, state: OrchestratorState, _config: object | None = None) -> OrchestratorState:
        if state.get("edited_plan"):
            plan = Plan.from_dict(state["edited_plan"])
            validate_plan(plan, max_steps=settings.orchestrator_max_steps, registry=self.registry)
            state = {**state, "plan": plan.to_dict(), "needs_approval": plan.has_writes}
        if state.get("needs_approval") and not state.get("approved"):
            self.emit(
                OrchestratorEvent(
                    type="awaiting_approval",
                    run_id=state["run_id"],
                    payload={
                        "plan": state.get("plan") or {},
                        "actions": ["run", "edit", "cancel"],
                    },
                )
            )
            return {"outcome": "awaiting_approval"}
        return {"outcome": "ok"}

    def dispatch(self, state: OrchestratorState, _config: object | None = None) -> OrchestratorState:
        if self.is_cancelled():
            return {"outcome": "cancelled"}
        self._thinking(state["run_id"], "Running the plan.")
        plan = Plan.from_dict(state.get("plan"))
        context = AgentContext(
            session=self.session,
            business_id=state["business_id"],
            user_id=state["user_id"],
            role=state["role"],
            run_id=state["run_id"],
        )
        results = dispatch_plan(
            plan,
            context=context,
            run_id=state["run_id"],
            timeout_seconds=settings.orchestrator_step_timeout_seconds,
            retries=settings.orchestrator_step_retries,
            is_cancelled=self.is_cancelled,
            registry=self.registry,
            emit=self.emit,
        )
        dumped = {key: value.model_dump() for key, value in results.items()}
        if self.is_cancelled():
            return {"results": dumped, "outcome": "cancelled"}
        return {"results": dumped, "outcome": "ok"}

    def aggregate(self, state: OrchestratorState, _config: object | None = None) -> OrchestratorState:
        self._thinking(state["run_id"], "Collecting results.")
        raw = state.get("results") or {}
        results = {key: TypedResult.model_validate(value) for key, value in raw.items()}
        cards = [item.to_card() for item in results.values() if item.status != "skipped"]
        if state.get("outcome") == "cancelled":
            return {"cards": cards, "summary": "The run was cancelled."}
        summary = write_summary(
            self.gateway,
            business_id=state["business_id"],
            run_id=state["run_id"],
            results=results,
        )
        for chunk in _token_chunks(summary):
            self.emit(OrchestratorEvent(type="token", run_id=state["run_id"], payload={"text": chunk}))
        for card in cards:
            self.emit(OrchestratorEvent(type="card", run_id=state["run_id"], payload={"card": card}))
        return {"cards": cards, "summary": summary}

    def reply(self, state: OrchestratorState, _config: object | None = None) -> OrchestratorState:
        card = state.get("understand_card")
        if card and state.get("outcome") in {"clarify", "refuse"}:
            self.emit(OrchestratorEvent(type="card", run_id=state["run_id"], payload={"card": card}))
            text = str(card.get("message") or "")
            self.emit(OrchestratorEvent(type="token", run_id=state["run_id"], payload={"text": text}))
            self.emit(
                OrchestratorEvent(
                    type="done",
                    run_id=state["run_id"],
                    payload={"status": "completed", "summary": text},
                )
            )
            return {"summary": text, "reply": text, "cards": [card]}
        if state.get("outcome") == "cancelled":
            self.emit(OrchestratorEvent(type="cancelled", run_id=state["run_id"], payload={}))
            return {"reply": "The run was cancelled."}
        summary = state.get("summary") or template_summary({})
        self.emit(
            OrchestratorEvent(
                type="done",
                run_id=state["run_id"],
                payload={"status": "completed", "summary": summary},
            )
        )
        return {"reply": summary}


def _token_chunks(text: str) -> list[str]:
    if not text:
        return []
    parts = text.split(" ")
    chunks: list[str] = []
    for index, part in enumerate(parts):
        chunks.append(part if index == 0 else f" {part}")
    return chunks


def route_after_understand(state: OrchestratorState) -> str:
    if state.get("resume_from") == "dispatch":
        return "dispatch"
    if state.get("outcome") in {"clarify", "refuse"}:
        return "reply"
    return "validate"


def route_after_validate(state: OrchestratorState) -> str:
    if state.get("outcome") in {"clarify", "refuse"}:
        return "reply"
    return "plan"


def route_after_plan(state: OrchestratorState) -> str:
    if state.get("outcome") in {"clarify", "refuse"}:
        return "reply"
    return "approve_plan"


def route_after_approve(state: OrchestratorState) -> str:
    if state.get("outcome") == "awaiting_approval":
        return END
    return "dispatch"


def route_start(state: OrchestratorState) -> str:
    if state.get("resume_from") == "dispatch":
        return "dispatch"
    if state.get("resume_from") == "approve_plan":
        return "approve_plan"
    return "understand"


def build_graph(runtime: OrchestratorRuntime):
    graph = StateGraph(OrchestratorState)
    graph.add_node("understand", runtime.understand)
    graph.add_node("validate", runtime.validate)
    graph.add_node("plan", runtime.plan)
    graph.add_node("approve_plan", runtime.approve_plan)
    graph.add_node("dispatch", runtime.dispatch)
    graph.add_node("aggregate", runtime.aggregate)
    graph.add_node("reply", runtime.reply)
    graph.add_conditional_edges(
        START,
        route_start,
        {
            "understand": "understand",
            "dispatch": "dispatch",
            "approve_plan": "approve_plan",
        },
    )
    graph.add_conditional_edges(
        "understand",
        route_after_understand,
        {"validate": "validate", "reply": "reply", "dispatch": "dispatch"},
    )
    graph.add_conditional_edges("validate", route_after_validate, {"plan": "plan", "reply": "reply"})
    graph.add_conditional_edges(
        "plan",
        route_after_plan,
        {"approve_plan": "approve_plan", "reply": "reply"},
    )
    graph.add_conditional_edges(
        "approve_plan",
        route_after_approve,
        {"dispatch": "dispatch", END: END},
    )
    graph.add_edge("dispatch", "aggregate")
    graph.add_edge("aggregate", "reply")
    graph.add_edge("reply", END)
    return graph.compile()
