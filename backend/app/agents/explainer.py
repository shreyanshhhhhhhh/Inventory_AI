"""Explainer agent. Prose is grounded in stored evidence; invented numbers fall back to a template."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.base import BaseAgent
from app.agents.context import AgentContext
from app.agents.errors import AgentError
from app.agents.tools import GetEvidenceOutput, GetHistoryOutput, GetRunTraceOutput, WhatIfOutput
from app.core.jsonutil import jsonable
from app.llm.prompts.registry import get_prompt
from app.llm.providers.base import ChatMessage
from app.llm.security import DATA_BLOCK_INSTRUCTIONS, wrap_untrusted
from app.orchestrator.types import TypedResult
from app.services.explainer import (
    explanation_is_grounded,
    parse_whatif_query,
    parse_why_target,
    template_explanation,
    template_whatif,
    what_would_change,
)


class ExplainerProse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    explanation: str = Field(default="")
    confidence: str = "medium"
    what_would_change: str = ""


def explainer_handler(
    task: str,
    params: dict[str, Any],
    inputs: dict[str, TypedResult],
    context: AgentContext,
) -> TypedResult:
    del inputs
    delay = params.get("_delay_seconds")
    if delay:
        time.sleep(float(delay))
    if params.get("_fail"):
        raise RuntimeError(str(params.get("_fail_message") or f"explainer.{task} failed"))
    agent = ExplainerAgent()
    agent.attach(context)
    return agent.typed_result(task, params, step_id=str(params.get("_step_id") or task))


class ExplainerAgent(BaseAgent):
    name = "explainer"
    description = "Explains suggestions, exceptions, and what-if scenarios from stored evidence only."
    allowed_tools = frozenset(
        {
            "get_suggestion",
            "get_run_trace",
            "get_evidence",
            "get_history",
            "whatif_reorder",
        }
    )
    max_tool_calls = 8
    prompt_name = "explainer_explain"

    def execute(self, task: str, context: AgentContext) -> dict[str, object]:
        del context
        return self.typed_result(task, {}, step_id=task).to_card()

    def typed_result(self, task: str, params: dict[str, Any], *, step_id: str) -> TypedResult:
        if task == "whatif":
            return self._whatif(params, step_id=step_id)
        if task != "explain":
            return TypedResult(
                step_id=step_id,
                agent=self.name,
                task=task,
                status="failed",
                card_type="text",
                message=f"Unknown explainer task: {task}",
            )
        return self._explain(params, step_id=step_id)

    def _explain(self, params: dict[str, Any], *, step_id: str) -> TypedResult:
        query = _param_str(params, "query") or ""
        parsed = parse_why_target(query)
        try:
            evidence = self.invoke_tool(
                "get_evidence",
                {
                    "kind": _param_str(params, "kind") or parsed["kind"],
                    "target_id": _param_str(params, "target_id", "suggestion_id", "exception_id", "purchase_order_id")
                    or parsed["target_id"],
                    "query": query or None,
                    "product_id": _param_str(params, "product_id"),
                    "suggestion_id": _param_str(params, "suggestion_id"),
                    "exception_id": _param_str(params, "exception_id"),
                    "purchase_order_id": _param_str(params, "purchase_order_id"),
                },
            )
        except AgentError as exc:
            return _failed(step_id, "explain", exc.detail)
        assert isinstance(evidence, GetEvidenceOutput)
        packet = evidence.model_dump()
        packet["query"] = query
        if evidence.run_id:
            try:
                trace = self.invoke_tool("get_run_trace", {"run_id": evidence.run_id})
                assert isinstance(trace, GetRunTraceOutput)
                packet["trace"] = [item.model_dump() for item in trace.items]
            except AgentError:
                pass
        product_id = _field_str(evidence.fields, "product_id") or _param_str(params, "product_id")
        if product_id:
            try:
                history = self.invoke_tool("get_history", {"product_id": product_id})
                assert isinstance(history, GetHistoryOutput)
                packet["history"] = history.model_dump()
            except AgentError:
                pass
        if not evidence.answerable:
            message = template_explanation(packet)
            return _explanation_result(step_id, message, packet, used_fallback=True)
        prose = self._wording("explainer_explain", packet)
        used_fallback = False
        if not prose.explanation or not explanation_is_grounded(prose.explanation, packet):
            message = template_explanation(packet)
            used_fallback = True
        else:
            message = prose.explanation.strip()
            if prose.what_would_change and explanation_is_grounded(prose.what_would_change, packet):
                message = f"{message} {prose.what_would_change.strip()}"
            else:
                message = f"{message} {what_would_change(evidence.fields)}"
        if prose.confidence:
            packet["confidence"] = prose.confidence
        packet["used_fallback"] = used_fallback
        return _explanation_result(step_id, message, packet, used_fallback=used_fallback)

    def _whatif(self, params: dict[str, Any], *, step_id: str) -> TypedResult:
        query = _param_str(params, "query") or ""
        parsed = parse_whatif_query(query)
        try:
            compare = self.invoke_tool(
                "whatif_reorder",
                {
                    "query": query or None,
                    "demand_pct": params.get("demand_pct", parsed["demand_pct"]),
                    "delay_days": params.get("delay_days", parsed["delay_days"]),
                    "lead_time_days": params.get("lead_time_days", parsed["lead_time_days"]),
                    "product_id": _param_str(params, "product_id"),
                },
            )
        except AgentError as exc:
            return _failed(step_id, "whatif", exc.detail)
        assert isinstance(compare, WhatIfOutput)
        packet = compare.model_dump()
        packet["query"] = query
        if not compare.answerable:
            return _whatif_result(step_id, template_whatif(packet), packet, used_fallback=True)
        prose = self._wording("explainer_whatif", packet)
        used_fallback = False
        if not prose.explanation or not explanation_is_grounded(prose.explanation, packet):
            message = template_whatif(packet)
            used_fallback = True
        else:
            message = prose.explanation.strip()
        packet["used_fallback"] = used_fallback
        packet["confidence"] = prose.confidence or "high"
        return _whatif_result(step_id, message, packet, used_fallback=used_fallback)

    def _wording(self, prompt_name: str, packet: dict[str, Any]) -> ExplainerProse:
        try:
            prompt = get_prompt(prompt_name)
            return self.call_llm_structured(
                [
                    ChatMessage(
                        role="system",
                        content=f"{prompt.template}\n{DATA_BLOCK_INSTRUCTIONS}",
                    ),
                    ChatMessage(role="user", content=wrap_untrusted(packet, label="evidence")),
                ],
                ExplainerProse,
                prompt_name=prompt_name,
            )
        except Exception:
            return ExplainerProse()


def _param_str(params: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = params.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _field_str(fields: dict[str, Any], key: str) -> str | None:
    value = fields.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _failed(step_id: str, task: str, message: str) -> TypedResult:
    return TypedResult(
        step_id=step_id,
        agent="explainer",
        task=task,
        status="ok",
        card_type="explanation",
        data={"answerable": False, "missing": [message], "evidence": {}, "citations": []},
        message=message,
    )


def _explanation_result(
    step_id: str,
    message: str,
    packet: dict[str, Any],
    *,
    used_fallback: bool,
) -> TypedResult:
    data = jsonable(
        {
            **packet,
            "used_fallback": used_fallback,
            "what_would_change": what_would_change(packet.get("fields") if isinstance(packet.get("fields"), dict) else {}),
        }
    )
    return TypedResult(
        step_id=step_id,
        agent="explainer",
        task="explain",
        status="ok",
        card_type="explanation",
        data=data if isinstance(data, dict) else {},
        message=message,
    )


def _whatif_result(
    step_id: str,
    message: str,
    packet: dict[str, Any],
    *,
    used_fallback: bool,
) -> TypedResult:
    data = jsonable({**packet, "used_fallback": used_fallback})
    return TypedResult(
        step_id=step_id,
        agent="explainer",
        task="whatif",
        status="ok",
        card_type="whatif_compare",
        data=data if isinstance(data, dict) else {},
        message=message,
    )
