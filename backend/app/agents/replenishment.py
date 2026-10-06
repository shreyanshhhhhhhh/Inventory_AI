"""Replenishment agent. Quantities and costs come from services, never from the model."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.base import BaseAgent
from app.agents.context import AgentContext
from app.agents.errors import AgentError
from app.agents.tools import (
    OpenPoOutput,
    ReorderOutput,
    SuggestionOutput,
    SupplierReliabilityOutput,
)
from app.core.config import settings
from app.core.jsonutil import jsonable
from app.llm.prompts.registry import get_prompt
from app.llm.providers.base import ChatMessage
from app.llm.security import DATA_BLOCK_INSTRUCTIONS, wrap_untrusted
from app.orchestrator.types import TypedResult

_LATE_SCORE = Decimal("0.7")
_READY = Decimal("0.90")
_MISSING = Decimal("0.40")


class ReplenishmentDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prefer_alternate: bool = False
    confidence: float = 1
    product_ids: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)


@dataclass
class PlannedLine:
    product_id: str
    sku: str
    quantity: Decimal
    unit_cost: Decimal
    supplier_id: str
    supplier_name: str
    reason_codes: list[str]
    evidence: dict[str, object]


@dataclass
class ReplenishmentPlan:
    lines: list[PlannedLine] = field(default_factory=list)
    confidence: Decimal = Decimal("0")
    caveats: list[str] = field(default_factory=list)
    message: str = ""
    ask_user: bool = False
    write: bool = False


def replenishment_handler(
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
        raise RuntimeError(str(params.get("_fail_message") or f"replenishment.{task} failed"))
    agent = ReplenishmentAgent()
    agent.attach(context)
    return agent.typed_result(task, params, step_id=str(params.get("_step_id") or task))


class ReplenishmentAgent(BaseAgent):
    name = "replenishment"
    description = "Turns reorder recommendations into purchase suggestions. Does not compute quantities."
    allowed_tools = frozenset(
        {
            "reorder_recommendations",
            "get_supplier_reliability",
            "get_open_pos",
            "create_po_suggestion",
        }
    )
    max_tool_calls = 16
    prompt_name = "replenishment_decide"

    def execute(self, task: str, context: AgentContext) -> dict[str, object]:
        del context
        return self.typed_result(task, {}, step_id=task).to_card()

    def typed_result(self, task: str, params: dict[str, Any], *, step_id: str) -> TypedResult:
        if task not in {"recommend", "draft_po"}:
            return TypedResult(
                step_id=step_id,
                agent=self.name,
                task=task,
                status="failed",
                card_type="text",
                message=f"Unknown replenishment task: {task}",
            )
        try:
            plan = self._plan(params, write=task == "draft_po")
        except AgentError as exc:
            return TypedResult(
                step_id=step_id,
                agent=self.name,
                task=task,
                status="failed",
                card_type="text",
                message=exc.detail,
            )
        if task == "recommend" or not plan.write:
            return _result(
                step_id=step_id,
                task=task,
                card_type="text",
                message=plan.message,
                plan=plan,
                suggestions=[],
            )
        return self._draft(step_id, plan)

    def _plan(self, params: dict[str, Any], *, write: bool) -> ReplenishmentPlan:
        recommendations = self.invoke_tool("reorder_recommendations", {})
        assert isinstance(recommendations, ReorderOutput)
        if not recommendations.items:
            return ReplenishmentPlan(
                confidence=Decimal("1"),
                message="No SKUs need a reorder.",
            )
        reliability = self.invoke_tool("get_supplier_reliability", {})
        open_pos = self.invoke_tool("get_open_pos", {})
        assert isinstance(reliability, SupplierReliabilityOutput)
        assert isinstance(open_pos, OpenPoOutput)
        rows = [item.model_dump() for item in recommendations.items]
        reliability_rows = [item.model_dump() for item in reliability.items]
        open_rows = [item.model_dump() for item in open_pos.items]
        decision = _default_decision()
        if _any_active_supplier(rows):
            decision = self._decide(rows, reliability_rows, open_rows)
        selected = _select_rows(rows, decision.product_ids)
        forced = _param_str(params, "supplier_id") if write else None
        return _assemble(
            selected,
            reliability_by_id={row["supplier_id"]: row for row in reliability_rows},
            covered=_covered_quantities(open_rows),
            prefer_alternate=decision.prefer_alternate and forced is None,
            forced_supplier_id=forced,
            llm_confidence=_clamp_confidence(decision.confidence),
        )

    def _decide(
        self,
        rows: list[dict[str, Any]],
        reliability_rows: list[dict[str, Any]],
        open_rows: list[dict[str, Any]],
    ) -> ReplenishmentDecision:
        packet = {
            "recommendations": rows,
            "supplier_reliability": reliability_rows,
            "open_purchase_orders": open_rows,
        }
        try:
            prompt = get_prompt(self.prompt_name)
            return self.call_llm_structured(
                [
                    ChatMessage(
                        role="system",
                        content=f"{prompt.template}\n{DATA_BLOCK_INSTRUCTIONS}",
                    ),
                    ChatMessage(
                        role="user",
                        content=wrap_untrusted(packet, label="replenishment"),
                    ),
                ],
                ReplenishmentDecision,
                prompt_name=self.prompt_name,
            )
        except Exception:
            return _default_decision()

    def _draft(self, step_id: str, plan: ReplenishmentPlan) -> TypedResult:
        grouped: dict[str, list[PlannedLine]] = {}
        for line in plan.lines:
            grouped.setdefault(line.supplier_id, []).append(line)
        suggestions: list[dict[str, object]] = []
        try:
            for supplier_id, lines in grouped.items():
                supplier_name = lines[0].supplier_name
                reason_codes = _union_codes(lines)
                summary = _draft_message(lines)
                output = self.invoke_tool(
                    "create_po_suggestion",
                    {
                        "supplier_id": supplier_id,
                        "lines": [
                            {
                                "product_id": line.product_id,
                                "quantity": str(line.quantity),
                                "unit_cost": str(line.unit_cost),
                            }
                            for line in lines
                        ],
                        "reason_codes": reason_codes,
                        "evidence": [line.evidence for line in lines],
                        "confidence": str(plan.confidence),
                        "caveats": list(plan.caveats),
                        "title": f"Draft PO for {supplier_name}",
                        "summary": summary,
                        "notes": summary,
                    },
                )
                assert isinstance(output, SuggestionOutput)
                suggestions.append(
                    {
                        "id": output.id,
                        "status": output.status,
                        "supplier_id": supplier_id,
                        "supplier_name": supplier_name,
                    }
                )
        except AgentError as exc:
            return TypedResult(
                step_id=step_id,
                agent=self.name,
                task="draft_po",
                status="ok" if exc.code == "guardrail_rejected" else "failed",
                card_type="text",
                message=exc.detail,
            )
        message = _draft_message(plan.lines)
        if len(suggestions) > 1:
            message = f"{len(suggestions)} drafts. {message}"
        return _result(
            step_id=step_id,
            task="draft_po",
            card_type="po_suggestion",
            message=message,
            plan=plan,
            suggestions=suggestions,
        )


def _assemble(
    rows: list[dict[str, Any]],
    *,
    reliability_by_id: dict[str, dict[str, Any]],
    covered: dict[str, Decimal],
    prefer_alternate: bool,
    forced_supplier_id: str | None,
    llm_confidence: Decimal,
) -> ReplenishmentPlan:
    missing: list[str] = []
    unlinked: list[str] = []
    non_integer: list[str] = []
    already_covered: list[str] = []
    lines: list[PlannedLine] = []
    for row in rows:
        sku = str(row["sku"])
        active = [item for item in row.get("suppliers") or [] if item.get("is_active")]
        if forced_supplier_id is not None:
            options = [item for item in active if item.get("supplier_id") == forced_supplier_id]
            if not options:
                if active:
                    unlinked.append(sku)
                else:
                    missing.append(sku)
                continue
        else:
            options = active
        if not options:
            missing.append(sku)
            continue
        chosen = _choose_supplier(options, reliability_by_id, prefer_alternate=prefer_alternate)
        if chosen is None:
            missing.append(sku)
            continue
        quantity = Decimal(str(row["recommended_quantity"]))
        if not quantity.is_finite() or quantity <= 0 or quantity != quantity.to_integral_value():
            non_integer.append(f"{sku} {quantity}")
            continue
        if covered.get(str(row["product_id"]), Decimal("0")) >= quantity:
            already_covered.append(sku)
            continue
        preferred = next((item for item in options if item.get("is_preferred")), options[0])
        unit_cost = Decimal(str(chosen["unit_cost"]))
        codes = _reason_codes(row, chosen, preferred, reliability_by_id)
        lines.append(
            PlannedLine(
                product_id=str(row["product_id"]),
                sku=sku,
                quantity=quantity,
                unit_cost=unit_cost,
                supplier_id=str(chosen["supplier_id"]),
                supplier_name=str(chosen["supplier_name"]),
                reason_codes=codes,
                evidence=_evidence(row, chosen, preferred, reliability_by_id),
            )
        )

    if missing or non_integer or unlinked:
        parts: list[str] = []
        if missing:
            parts.append(
                "I need an active supplier and unit cost linked to these SKUs before I can draft a purchase order: "
                + ", ".join(missing)
                + "."
            )
        if unlinked:
            parts.append(
                "That supplier is not linked to the SKUs that need reordering: " + ", ".join(unlinked) + "."
            )
        if non_integer:
            parts.append(
                "Recommended quantity is not a whole number for "
                + ", ".join(non_integer)
                + ". I did not round it and I did not draft a purchase order."
            )
        return ReplenishmentPlan(
            confidence=_MISSING,
            caveats=[*missing, *unlinked, *non_integer],
            message=" ".join(parts),
            ask_user=True,
        )
    if not lines and already_covered:
        return ReplenishmentPlan(
            confidence=Decimal("1"),
            caveats=[f"open_po_covers:{sku}" for sku in already_covered],
            message="Open purchase orders already cover the SKUs that need a reorder: "
            + ", ".join(already_covered)
            + ".",
        )
    if not lines:
        return ReplenishmentPlan(
            confidence=_MISSING,
            message="I need a supplier and unit cost before I can draft a purchase order.",
            ask_user=True,
        )
    confidence = min(_READY, llm_confidence)
    threshold = Decimal(str(settings.orchestrator_confidence_min))
    if confidence < threshold:
        return ReplenishmentPlan(
            lines=lines,
            confidence=confidence,
            caveats=[f"open_po_covers:{sku}" for sku in already_covered],
            message=(
                "I am not confident enough to draft a purchase order. "
                "Tell me which supplier to use, for example /draft-po <supplier name>."
            ),
            ask_user=True,
        )
    caveats = [f"open_po_covers:{sku}" for sku in already_covered]
    return ReplenishmentPlan(
        lines=lines,
        confidence=confidence,
        caveats=caveats,
        message=_draft_message(lines),
        write=True,
    )


def _choose_supplier(
    options: list[dict[str, Any]],
    reliability_by_id: dict[str, dict[str, Any]],
    *,
    prefer_alternate: bool,
) -> dict[str, Any] | None:
    if not options:
        return None
    preferred = next((item for item in options if item.get("is_preferred")), options[0])
    if not prefer_alternate or not _is_late(reliability_by_id.get(str(preferred["supplier_id"]))):
        return preferred
    preferred_score = _score(reliability_by_id.get(str(preferred["supplier_id"])))
    better: list[tuple[Decimal, int, dict[str, Any]]] = []
    for option in options:
        if option["supplier_id"] == preferred["supplier_id"]:
            continue
        score = _score(reliability_by_id.get(str(option["supplier_id"])))
        if score > preferred_score:
            better.append((score, int(option["lead_time_days"]), option))
    if not better:
        return preferred
    better.sort(key=lambda item: (-item[0], item[1]))
    return better[0][2]


def _reason_codes(
    row: dict[str, Any],
    chosen: dict[str, Any],
    preferred: dict[str, Any],
    reliability_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    codes = ["LOW_COVER"]
    reorder_point = Decimal(str(row["reorder_point"] or 0))
    forecast_units = Decimal(str(row["forecast_units"]))
    if forecast_units > reorder_point and forecast_units > 0:
        codes.append("FORECAST_UP")
    watched = {str(chosen["supplier_id"]), str(preferred["supplier_id"])}
    if any(_is_late(reliability_by_id.get(supplier_id)) for supplier_id in watched):
        codes.append("SUPPLIER_LATE")
    if not chosen.get("is_preferred"):
        codes.append("ALTERNATE_SUPPLIER")
    return codes


def _evidence(
    row: dict[str, Any],
    chosen: dict[str, Any],
    preferred: dict[str, Any],
    reliability_by_id: dict[str, dict[str, Any]],
) -> dict[str, object]:
    chosen_rel = reliability_by_id.get(str(chosen["supplier_id"]))
    preferred_rel = reliability_by_id.get(str(preferred["supplier_id"]))
    return {
        "sku": row["sku"],
        "product_id": row["product_id"],
        "on_hand": str(row["on_hand"]),
        "reorder_point": None if row["reorder_point"] is None else str(row["reorder_point"]),
        "safety_stock": None if row["safety_stock"] is None else str(row["safety_stock"]),
        "forecast_units": str(row["forecast_units"]),
        "recommended_quantity": str(row["recommended_quantity"]),
        "unit_cost": str(chosen["unit_cost"]),
        "lead_time_days": chosen["lead_time_days"],
        "supplier_id": chosen["supplier_id"],
        "supplier_name": chosen["supplier_name"],
        "reliability_score": None if chosen_rel is None else str(chosen_rel["reliability_score"]),
        "overdue_count": None if chosen_rel is None else chosen_rel["overdue_count"],
        "preferred_supplier_id": preferred["supplier_id"],
        "preferred_reliability_score": None
        if preferred_rel is None
        else str(preferred_rel["reliability_score"]),
        "preferred_overdue_count": None if preferred_rel is None else preferred_rel["overdue_count"],
    }


def _select_rows(rows: list[dict[str, Any]], product_ids: list[str]) -> list[dict[str, Any]]:
    if not product_ids:
        return rows
    real = {str(row["product_id"]) for row in rows}
    matched = {product_id for product_id in product_ids if product_id in real}
    if not matched:
        return rows
    return [row for row in rows if str(row["product_id"]) in matched]


def _covered_quantities(open_rows: list[dict[str, Any]]) -> dict[str, Decimal]:
    covered: dict[str, Decimal] = {}
    for order in open_rows:
        for line in order.get("lines") or []:
            product_id = str(line["product_id"])
            covered[product_id] = covered.get(product_id, Decimal("0")) + Decimal(
                str(line["quantity_ordered"])
            )
    return covered


def _any_active_supplier(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        for option in row.get("suppliers") or []:
            if option.get("is_active"):
                return True
    return False


def _is_late(row: dict[str, Any] | None) -> bool:
    if row is None:
        return False
    score = Decimal(str(row["reliability_score"]))
    return score < _LATE_SCORE or int(row["overdue_count"]) >= 1


def _score(row: dict[str, Any] | None) -> Decimal:
    if row is None:
        return Decimal("1")
    return Decimal(str(row["reliability_score"]))


def _clamp_confidence(value: float) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except Exception:
        return Decimal("0")
    if not parsed.is_finite() or parsed < 0:
        return Decimal("0")
    if parsed > 1:
        return Decimal("1")
    return parsed


def _default_decision() -> ReplenishmentDecision:
    return ReplenishmentDecision()


def _union_codes(lines: list[PlannedLine]) -> list[str]:
    found: list[str] = []
    for line in lines:
        for code in line.reason_codes:
            if code not in found:
                found.append(code)
    return found


def _draft_message(lines: list[PlannedLine]) -> str:
    parts = [
        f"{line.supplier_name}: {line.sku} qty {line.quantity} ({', '.join(line.reason_codes)})"
        for line in lines
    ]
    return "Draft for " + "; ".join(parts) + "."


def _param_str(params: dict[str, Any], key: str) -> str | None:
    value = params.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _result(
    *,
    step_id: str,
    task: str,
    card_type: str,
    message: str,
    plan: ReplenishmentPlan,
    suggestions: list[dict[str, object]],
) -> TypedResult:
    status = "approved" if suggestions and all(item["status"] == "approved" for item in suggestions) else "pending"
    if not suggestions:
        status = "pending"
    proposals = []
    grouped: dict[str, list[PlannedLine]] = {}
    for line in plan.lines:
        grouped.setdefault(line.supplier_id, []).append(line)
    for supplier_id, lines in grouped.items():
        proposals.append(
            {
                "supplier_id": supplier_id,
                "lines": [
                    {
                        "product_id": line.product_id,
                        "sku": line.sku,
                        "quantity": str(line.quantity),
                        "unit_cost": str(line.unit_cost),
                    }
                    for line in lines
                ],
            }
        )
    card_lines = [
        {
            "product_id": line.product_id,
            "sku": line.sku,
            "quantity": str(line.quantity),
            "unit_cost": str(line.unit_cost),
            "supplier_id": line.supplier_id,
        }
        for line in plan.lines
    ]
    data = jsonable(
        {
            "lines": card_lines,
            "proposals": proposals if plan.write else [],
            "reason_codes": _union_codes(plan.lines),
            "evidence": [line.evidence for line in plan.lines],
            "confidence": str(plan.confidence),
            "caveats": plan.caveats,
            "suggestions": suggestions,
            "suggestion_id": suggestions[0]["id"] if suggestions else None,
            "suggestion_status": status if suggestions else None,
            "ask_user": plan.ask_user,
        }
    )
    return TypedResult(
        step_id=step_id,
        agent="replenishment",
        task=task,
        status="ok",
        card_type=card_type,  # type: ignore[arg-type]
        data=data if isinstance(data, dict) else {},
        message=message,
    )
