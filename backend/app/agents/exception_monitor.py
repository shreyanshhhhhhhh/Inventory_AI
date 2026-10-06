from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.base import BaseAgent
from app.agents.context import AgentContext
from app.agents.playbooks import clip_action
from app.agents.tools import RecordExceptionActionsOutput, ScanDetectorsOutput
from app.core.jsonutil import jsonable
from app.llm.prompts.registry import get_prompt
from app.llm.providers.base import ChatMessage
from app.llm.security import DATA_BLOCK_INSTRUCTIONS, wrap_untrusted
from app.orchestrator.types import TypedResult


class ExceptionActionRanking(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dedupe_key: str
    action: str
    rationale: str = Field(max_length=280)


class ExceptionRankOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rankings: list[ExceptionActionRanking] = Field(default_factory=list)


class ExceptionMonitorAgent(BaseAgent):
    name = "exception_monitor"
    description = "Deterministic exception scan. The LLM only ranks playbook actions."
    allowed_tools = frozenset({"scan_detectors", "record_exception_actions"})
    max_tool_calls = 4
    prompt_name = "exception_rank"

    def execute(self, task: str, context: AgentContext) -> dict[str, object]:
        del context
        result = self.typed_result(task, {}, step_id=task)
        return result.to_card()

    def typed_result(
        self,
        task: str,
        params: dict[str, Any],
        *,
        step_id: str,
    ) -> TypedResult:
        del params
        if task != "scan":
            return TypedResult(
                step_id=step_id,
                agent=self.name,
                task=task,
                status="failed",
                card_type="text",
                message=f"Unknown exception monitor task: {task}",
            )
        detected = self.invoke_tool("scan_detectors", {})
        assert isinstance(detected, ScanDetectorsOutput)
        rankings = self._rank(detected.items)
        recorded = self.invoke_tool("record_exception_actions", {"rankings": rankings})
        assert isinstance(recorded, RecordExceptionActionsOutput)
        items = [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "message": item.get("title"),
                "severity": item.get("severity"),
                "exception_type": item.get("exception_type"),
                "recommended_action": item.get("recommended_action"),
                "rationale": item.get("rationale"),
                "dedupe_key": item.get("dedupe_key"),
                "evidence": item.get("evidence"),
            }
            for item in recorded.items
        ]
        data = jsonable({"items": items})
        if not items:
            message = "No exceptions in this shop."
        else:
            message = f"{len(items)} exception findings."
        return TypedResult(
            step_id=step_id,
            agent=self.name,
            task="scan",
            status="ok",
            card_type="exception_list",
            data=data if isinstance(data, dict) else {},
            message=message,
        )

    def _rank(self, findings: list[dict[str, Any]]) -> list[dict[str, str]]:
        if not findings:
            return []
        prompt = get_prompt(self.prompt_name)
        try:
            parsed = self.call_llm_structured(
                [
                    ChatMessage(
                        role="system",
                        content=f"{prompt.template}\n{DATA_BLOCK_INSTRUCTIONS}",
                    ),
                    ChatMessage(
                        role="user",
                        content=wrap_untrusted({"findings": findings}, label="findings"),
                    ),
                ],
                ExceptionRankOutput,
                prompt_name=self.prompt_name,
            )
            by_key = {item.dedupe_key: item for item in parsed.rankings}
        except Exception:
            by_key = {}
        rankings: list[dict[str, str]] = []
        for finding in findings:
            key = str(finding.get("dedupe_key") or "")
            allowed = [str(item) for item in finding.get("candidate_actions") or []]
            chosen = by_key.get(key)
            action = clip_action(chosen.action if chosen is not None else None, allowed)
            rationale = (chosen.rationale.strip() if chosen is not None else "") or "Playbook default."
            rankings.append({"dedupe_key": key, "action": action, "rationale": rationale})
        return rankings


def exception_monitor_handler(
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
        raise RuntimeError(str(params.get("_fail_message") or "exception_monitor.scan failed"))
    agent = ExceptionMonitorAgent()
    agent.attach(context)
    return agent.typed_result(task, params, step_id=str(params.get("_step_id") or task))
