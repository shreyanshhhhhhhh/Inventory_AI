"""Supplier communication agent. The LLM writes tone; numbers come from tools."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.agents.base import BaseAgent
from app.agents.context import AgentContext
from app.agents.errors import AgentError
from app.agents.tools import GetExceptionOutput, GetPoOutput, GetSupplierOutput, SuggestionOutput
from app.core.jsonutil import jsonable
from app.llm.prompts.registry import get_prompt
from app.llm.providers.base import ChatMessage
from app.llm.security import DATA_BLOCK_INSTRUCTIONS, wrap_untrusted
from app.orchestrator.types import TypedResult
from app.services.email_sender import sender_status
from app.services.supplier_email import draft_is_grounded, facts_from_po, normalize_kind, render_template
from app.services.supplier_messages import latest_open_po_for_supplier


class EmailWording(BaseModel):
    model_config = ConfigDict(extra="ignore")

    greeting: str = ""
    ask: str = ""
    closing: str = ""


def supplier_comm_handler(
    task: str,
    params: dict[str, Any],
    inputs: dict[str, TypedResult],
    context: AgentContext,
) -> TypedResult:
    delay = params.get("_delay_seconds")
    if delay:
        time.sleep(float(delay))
    if params.get("_fail"):
        raise RuntimeError(str(params.get("_fail_message") or f"supplier_comm.{task} failed"))
    agent = SupplierCommAgent()
    agent.attach(context)
    return agent.typed_result(task, params, inputs, step_id=str(params.get("_step_id") or task))


class SupplierCommAgent(BaseAgent):
    name = "supplier_comm"
    description = "Drafts supplier emails from order facts. Never sends mail."
    allowed_tools = frozenset({"get_po", "get_supplier", "get_exception", "draft_email"})
    max_tool_calls = 8
    prompt_name = "supplier_comm_wording"

    def execute(self, task: str, context: AgentContext) -> dict[str, object]:
        del context
        return self.typed_result(task, {}, {}, step_id=task).to_card()

    def typed_result(
        self,
        task: str,
        params: dict[str, Any],
        inputs: dict[str, TypedResult],
        *,
        step_id: str,
    ) -> TypedResult:
        if task != "draft_emails":
            return TypedResult(
                step_id=step_id,
                agent=self.name,
                task=task,
                status="failed",
                card_type="text",
                message=f"Unknown supplier communication task: {task}",
            )
        supplier_id = _param_str(params, "supplier_id") or _supplier_from_inputs(inputs)
        if not supplier_id:
            return _ask(
                step_id,
                "Tell me which supplier to email, for example /email <supplier> chase.",
            )
        try:
            supplier_out = self.invoke_tool("get_supplier", {"supplier_id": supplier_id})
            assert isinstance(supplier_out, GetSupplierOutput)
            po_id = _param_str(params, "po_id")
            po_out = self._load_po(supplier_id=supplier_id, po_id=po_id)
            exception_out = self._load_exception(_param_str(params, "exception_id"))
        except AgentError as exc:
            return TypedResult(
                step_id=step_id,
                agent=self.name,
                task=task,
                status="failed",
                card_type="text",
                message=exc.detail,
            )
        kind = normalize_kind(_param_str(params, "kind"))
        if _param_str(params, "kind") is None:
            kind = _default_kind(po_out)
        extra = _extra_facts(params, exception_out)
        facts = facts_from_po(
            supplier=supplier_out.model_dump(),
            po=None if po_out is None else _po_dict(po_out),
            kind=kind,
            extra=extra,
        )
        wording = self._wording(facts)
        greeting, ask, closing = wording.greeting, wording.ask, wording.closing
        subject, body = render_template(facts, greeting=greeting, ask=ask, closing=closing)
        if not draft_is_grounded(subject, body, facts):
            wording = self._wording(facts)
            greeting, ask, closing = wording.greeting, wording.ask, wording.closing
            subject, body = render_template(facts, greeting=greeting, ask=ask, closing=closing)
            if not draft_is_grounded(subject, body, facts):
                greeting, ask, closing = "", "", ""
        try:
            drafted = self.invoke_tool(
                "draft_email",
                {
                    "supplier_id": supplier_id,
                    "kind": kind,
                    "po_id": None if po_out is None else po_out.id,
                    "greeting": greeting,
                    "ask": ask,
                    "closing": closing,
                    "delay_days": extra.get("delay_days"),
                    "exception_id": None if exception_out is None else exception_out.id,
                },
            )
        except AgentError as exc:
            return TypedResult(
                step_id=step_id,
                agent=self.name,
                task=task,
                status="failed",
                card_type="text",
                message=exc.detail,
            )
        assert isinstance(drafted, SuggestionOutput)
        payload = drafted.payload if isinstance(drafted.payload, dict) else {}
        mail = sender_status()
        data = jsonable(
            {
                "suggestion_id": drafted.id,
                "suggestion_status": drafted.status,
                "message_id": payload.get("message_id"),
                "to_email": payload.get("to_email") or supplier_out.email,
                "subject": payload.get("subject"),
                "body": payload.get("body"),
                "kind": payload.get("kind") or kind,
                "supplier_id": supplier_id,
                "supplier_name": supplier_out.name,
                "po_id": payload.get("po_id"),
                "po_number": payload.get("po_number") or facts.get("po_number"),
                "console_mode": mail.get("console_mode"),
                "banner": mail.get("banner"),
                "used_template": payload.get("used_template"),
            }
        )
        return TypedResult(
            step_id=step_id,
            agent=self.name,
            task=task,
            status="ok",
            card_type="email_draft",
            data=data if isinstance(data, dict) else {},
            message=str(payload.get("subject") or f"Draft {kind} email to {supplier_out.name}"),
        )

    def _load_po(self, *, supplier_id: str, po_id: str | None) -> GetPoOutput | None:
        chosen = po_id
        if chosen is None:
            context = self._require_context()
            latest = latest_open_po_for_supplier(
                context.session,
                business_id=context.business_id,
                supplier_id=supplier_id,
            )
            if latest is None:
                return None
            chosen = str(latest["id"])
        output = self.invoke_tool("get_po", {"purchase_order_id": chosen})
        assert isinstance(output, GetPoOutput)
        return output

    def _load_exception(self, exception_id: str | None) -> GetExceptionOutput | None:
        if not exception_id:
            return None
        output = self.invoke_tool("get_exception", {"exception_id": exception_id})
        assert isinstance(output, GetExceptionOutput)
        return output

    def _wording(self, facts: dict[str, object]) -> EmailWording:
        packet = {
            "kind": facts.get("kind"),
            "supplier_name": facts.get("supplier_name"),
            "instruction": "Write greeting, ask, and closing only. Do not include numbers, dates, or PO numbers.",
        }
        try:
            prompt = get_prompt(self.prompt_name)
            return self.call_llm_structured(
                [
                    ChatMessage(
                        role="system",
                        content=f"{prompt.template}\n{DATA_BLOCK_INSTRUCTIONS}",
                    ),
                    ChatMessage(role="user", content=wrap_untrusted(packet, label="email_facts")),
                ],
                EmailWording,
                prompt_name=self.prompt_name,
            )
        except Exception:
            return EmailWording()


def _param_str(params: dict[str, Any], key: str) -> str | None:
    value = params.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _supplier_from_inputs(inputs: dict[str, TypedResult]) -> str | None:
    for result in inputs.values():
        data = result.data if isinstance(result.data, dict) else {}
        for item in data.get("items") or []:
            if not isinstance(item, dict):
                continue
            evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
            supplier_id = item.get("supplier_id") or evidence.get("supplier_id")
            if isinstance(supplier_id, str) and supplier_id:
                return supplier_id
        for line in data.get("lines") or []:
            if isinstance(line, dict) and isinstance(line.get("supplier_id"), str) and line["supplier_id"]:
                return str(line["supplier_id"])
    return None


def _default_kind(po: GetPoOutput | None) -> str:
    if po is not None and po.status in {"sent", "approved"}:
        return "chase"
    return "order"


def _extra_facts(params: dict[str, Any], exception: GetExceptionOutput | None) -> dict[str, object]:
    extra: dict[str, object] = {}
    delay = params.get("delay_days")
    if delay is not None:
        extra["delay_days"] = delay
    if exception is not None:
        extra["exception_title"] = exception.title
        evidence = exception.evidence
        if "delay_days" not in extra and evidence.get("days_overdue") is not None:
            extra["delay_days"] = evidence.get("days_overdue")
    return extra


def _po_dict(po: GetPoOutput) -> dict[str, object]:
    return {
        "id": po.id,
        "po_number": po.po_number,
        "supplier_id": po.supplier_id,
        "expected_date": po.expected_date,
        "line_items": [
            {
                "product_id": line.product_id,
                "product_name": line.product_name,
                "quantity": line.quantity,
            }
            for line in po.line_items
        ],
    }


def _ask(step_id: str, message: str) -> TypedResult:
    return TypedResult(
        step_id=step_id,
        agent="supplier_comm",
        task="draft_emails",
        status="ok",
        card_type="text",
        data={"ask_user": True},
        message=message,
    )
