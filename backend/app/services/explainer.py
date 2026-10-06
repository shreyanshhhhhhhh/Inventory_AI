"""Evidence lookup, grounding, and templated explanations. The LLM never invents numbers."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.jsonutil import jsonable
from app.models import AgentStep, AgentSuggestion, PurchaseOrder
from app.orchestrator.aggregate import numbers_in_text
from app.services import agent_suggestions as suggestion_service
from app.services.exceptions import ExceptionError, get_exception
from app.services.forecast import ForecastError, get_history, list_forecasts
from app.services.purchase_orders import PurchaseOrderError, get_po
from app.services.replenishment import whatif_compare

_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_PO_NUM_RE = re.compile(r"\bPO-\d+\b", re.IGNORECASE)
_DEMAND_DOWN_RE = re.compile(r"demand\s+down\s+(\d+(?:\.\d+)?)\s*%?", re.IGNORECASE)
_DEMAND_UP_RE = re.compile(r"demand\s+up\s+(\d+(?:\.\d+)?)\s*%?", re.IGNORECASE)
_DEMAND_SIGNED_RE = re.compile(r"demand\s+([+-]\d+(?:\.\d+)?)\s*%?", re.IGNORECASE)
_DELAY_RE = re.compile(
    r"(?:supplier\s+)?delay(?:ed|s)?(?:\s+of)?\s+(\d+)\s+days?",
    re.IGNORECASE,
)
_LEAD_RE = re.compile(
    r"lead[\s-]*time(?:\s+(?:to|of|change(?:s)?(?:\s+to)?))?\s+(\d+)\s+days?",
    re.IGNORECASE,
)


class ExplainerError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, code: str = "bad_request") -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


def parse_why_target(text: str) -> dict[str, str | None]:
    raw = (text or "").strip()
    lowered = raw.lower()
    kind: str | None = None
    if re.search(r"\bexceptions?\b", lowered):
        kind = "exception"
    elif re.search(r"\bsuggestions?\b", lowered):
        kind = "suggestion"
    elif re.search(r"\b(purchase[_\s-]?order|\bpos?\b)\b", lowered):
        kind = "po"
    uuid = _UUID_RE.search(raw)
    po_num = _PO_NUM_RE.search(raw)
    target = uuid.group(0) if uuid else (po_num.group(0).upper() if po_num else None)
    return {"kind": kind, "target_id": target, "query": raw}


def parse_whatif_query(text: str) -> dict[str, object]:
    raw = (text or "").strip()
    demand_pct: Decimal | None = None
    if down := _DEMAND_DOWN_RE.search(raw):
        demand_pct = -Decimal(down.group(1))
    elif up := _DEMAND_UP_RE.search(raw):
        demand_pct = Decimal(up.group(1))
    elif signed := _DEMAND_SIGNED_RE.search(raw):
        demand_pct = Decimal(signed.group(1))
    delay_match = _DELAY_RE.search(raw)
    lead_match = _LEAD_RE.search(raw)
    return {
        "demand_pct": demand_pct,
        "delay_days": int(delay_match.group(1)) if delay_match else None,
        "lead_time_days": int(lead_match.group(1)) if lead_match else None,
        "query": raw,
    }


def get_run_trace(
    session: Session,
    *,
    business_id: str,
    run_id: str,
) -> list[dict[str, object]]:
    rows = session.scalars(
        select(AgentStep)
        .where(AgentStep.business_id == business_id, AgentStep.run_id == run_id)
        .order_by(AgentStep.created_at.asc())
    ).all()
    return [
        {
            "id": row.id,
            "step_kind": row.step_kind,
            "tool_name": row.tool_name,
            "prompt_name": row.prompt_name,
            "duration_ms": row.duration_ms,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def collect_evidence(
    session: Session,
    *,
    business_id: str,
    kind: str | None = None,
    target_id: str | None = None,
    query: str | None = None,
    product_id: str | None = None,
    suggestion_id: str | None = None,
    exception_id: str | None = None,
    purchase_order_id: str | None = None,
) -> dict[str, object]:
    parsed = parse_why_target(query or "")
    resolved_kind = kind or parsed["kind"]
    resolved_id = target_id or suggestion_id or exception_id or purchase_order_id or parsed["target_id"]
    if resolved_kind == "suggestion" or (resolved_kind is None and resolved_id and _looks_like_suggestion(session, business_id, resolved_id)):
        return _evidence_for_suggestion(session, business_id=business_id, suggestion_id=str(resolved_id))
    if resolved_kind == "exception":
        return _evidence_for_exception(session, business_id=business_id, exception_id=str(resolved_id or ""))
    if resolved_kind == "po":
        return _evidence_for_po(session, business_id=business_id, purchase_order_id=str(resolved_id or ""))
    if resolved_id:
        for loader in (_evidence_for_suggestion, _evidence_for_exception, _evidence_for_po):
            try:
                packet = loader(session, business_id=business_id, **_loader_kwargs(loader, str(resolved_id)))
            except ExplainerError:
                continue
            if packet.get("answerable"):
                return packet
    if product_id:
        return _evidence_for_product(session, business_id=business_id, product_id=product_id)
    latest = _latest_suggestion(session, business_id)
    if latest is not None:
        return _evidence_for_suggestion(session, business_id=business_id, suggestion_id=str(latest["id"]))
    return _unanswerable(
        ["suggestion, exception, or purchase order id"],
        subject="I cannot answer from stored evidence.",
    )


def explanation_is_grounded(text: str, evidence: dict[str, object]) -> bool:
    allowed_dates = dates_in_value(evidence)
    for found in _DATE_RE.findall(text):
        if found not in allowed_dates:
            return False
    remainder = _DATE_RE.sub(" ", text)
    allowed_numbers = numbers_in_value(evidence)
    for number in numbers_in_text(remainder):
        if number not in allowed_numbers and not _close_match(number, allowed_numbers):
            return False
    return True


def numbers_in_value(value: Any) -> set[Decimal]:
    found: set[Decimal] = set()

    def walk(item: Any) -> None:
        if isinstance(item, bool):
            return
        if isinstance(item, int):
            found.add(Decimal(item))
            return
        if isinstance(item, float):
            found.add(Decimal(str(item)))
            return
        if isinstance(item, Decimal):
            found.add(item)
            return
        if isinstance(item, str):
            try:
                found.add(Decimal(item))
            except InvalidOperation:
                for number in numbers_in_text(item):
                    found.add(number)
            return
        if isinstance(item, dict):
            for nested in item.values():
                walk(nested)
            return
        if isinstance(item, list):
            for nested in item:
                walk(nested)

    walk(jsonable(value))
    return found


def dates_in_value(value: Any) -> set[str]:
    found: set[str] = set()

    def walk(item: Any) -> None:
        if isinstance(item, str):
            found.update(_DATE_RE.findall(item))
            return
        if isinstance(item, dict):
            for nested in item.values():
                walk(nested)
            return
        if isinstance(item, list):
            for nested in item:
                walk(nested)

    walk(jsonable(value))
    return found


def evidence_rows(blob: dict[str, object], *, source: str = "evidence") -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def walk(item: Any, path: str) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                walk(nested, f"{path}.{key}" if path else str(key))
            return
        if isinstance(item, list):
            for index, nested in enumerate(item):
                walk(nested, f"{path}[{index}]")
            return
        if item is None or item == "":
            return
        if isinstance(item, (str, int, float, Decimal)):
            rows.append({"field": path, "value": str(item), "source": source})

    walk(blob, "")
    return rows


def template_explanation(packet: dict[str, object]) -> str:
    if not packet.get("answerable"):
        missing = packet.get("missing") or []
        labels = ", ".join(str(item) for item in missing) if isinstance(missing, list) else "required evidence"
        return (
            f"I cannot answer from stored evidence. Missing: {labels}. "
            "Ask about a suggestion, exception, or purchase order that already has numbers on file."
        )
    fields = packet.get("fields") if isinstance(packet.get("fields"), dict) else {}
    subject = str(packet.get("subject") or "This decision")
    codes = fields.get("reason_codes") if isinstance(fields, dict) else None
    code_text = ""
    if isinstance(codes, list) and codes:
        code_text = " Reason codes: " + ", ".join(str(item) for item in codes) + "."
    quantity = fields.get("recommended_quantity") if isinstance(fields, dict) else None
    on_hand = fields.get("on_hand") if isinstance(fields, dict) else None
    forecast = fields.get("forecast_units") if isinstance(fields, dict) else None
    model = fields.get("chosen_model") or fields.get("forecast_method") if isinstance(fields, dict) else None
    lead = fields.get("lead_time_days") if isinstance(fields, dict) else None
    reliability = fields.get("reliability_score") if isinstance(fields, dict) else None
    confidence = fields.get("confidence") if isinstance(fields, dict) else packet.get("confidence")
    parts = [f"{subject} is grounded in stored evidence."]
    if quantity is not None:
        parts.append(f"Recommended quantity is {quantity}.")
    if on_hand is not None:
        parts.append(f"On-hand is {on_hand}.")
    if forecast is not None:
        parts.append(f"Forecast units are {forecast}.")
    if model:
        parts.append(f"Forecast model is {model}.")
    if lead is not None:
        parts.append(f"Lead time is {lead} days.")
    if reliability is not None:
        parts.append(f"Supplier reliability is {reliability}.")
    if confidence is not None:
        parts.append(f"Confidence is {confidence}.")
    parts.append(code_text.strip())
    parts.append(what_would_change(fields if isinstance(fields, dict) else {}))
    return " ".join(part for part in parts if part).strip()


def template_whatif(compare: dict[str, object]) -> str:
    if not compare.get("answerable"):
        missing = compare.get("missing") or ["scenario inputs"]
        labels = ", ".join(str(item) for item in missing) if isinstance(missing, list) else str(missing)
        return f"I cannot run that what-if from stored data. Missing: {labels}."
    items = compare.get("items")
    rows = items if isinstance(items, list) else []
    if not rows:
        return "The scenario did not change any SKU metrics."
    first = rows[0] if isinstance(rows[0], dict) else {}
    before = first.get("before") if isinstance(first.get("before"), dict) else {}
    after = first.get("after") if isinstance(first.get("after"), dict) else {}
    sku = first.get("sku") or "SKU"
    return (
        f"{sku} recommended quantity moves from {before.get('recommended_quantity')} to "
        f"{after.get('recommended_quantity')}. Stockout date moves from {before.get('stockout_date') or 'none'} "
        f"to {after.get('stockout_date') or 'none'}. Cost moves from {before.get('cost') or 'none'} "
        f"to {after.get('cost') or 'none'}."
    )


def what_would_change(fields: dict[str, object]) -> str:
    codes = fields.get("reason_codes")
    labels = [str(item) for item in codes] if isinstance(codes, list) else []
    hints: list[str] = []
    if "LOW_COVER" in labels or fields.get("on_hand") is not None:
        hints.append("higher on-hand or a lower reorder point")
    if "FORECAST_UP" in labels or fields.get("forecast_units") is not None:
        hints.append("a lower forecast")
    if "SUPPLIER_LATE" in labels or fields.get("reliability_score") is not None:
        hints.append("better supplier reliability")
    if "ALTERNATE_SUPPLIER" in labels:
        hints.append("the preferred supplier being on time")
    if not hints:
        hints.append("new on-hand, forecast, lead time, or supplier reliability")
    return "What would change the decision: " + ", ".join(hints) + "."


def run_whatif(
    session: Session,
    *,
    business_id: str,
    query: str | None = None,
    demand_pct: Decimal | None = None,
    delay_days: int | None = None,
    lead_time_days: int | None = None,
    product_id: str | None = None,
) -> dict[str, object]:
    parsed = parse_whatif_query(query or "")
    resolved_demand = demand_pct if demand_pct is not None else parsed["demand_pct"]
    resolved_delay = delay_days if delay_days is not None else parsed["delay_days"]
    resolved_lead = lead_time_days if lead_time_days is not None else parsed["lead_time_days"]
    if resolved_demand is None and resolved_delay is None and resolved_lead is None:
        return {
            "answerable": False,
            "missing": ["scenario (supplier delay of N days, demand up/down X percent, or lead time change)"],
            "scenario": {"demand_pct": None, "delay_days": None, "lead_time_days": None},
            "items": [],
        }
    return whatif_compare(
        session,
        business_id=business_id,
        demand_pct=Decimal(str(resolved_demand)) if resolved_demand is not None else None,
        delay_days=int(resolved_delay) if resolved_delay is not None else None,
        lead_time_days=int(resolved_lead) if resolved_lead is not None else None,
        product_id=product_id,
    )


def _evidence_for_suggestion(
    session: Session,
    *,
    business_id: str,
    suggestion_id: str,
) -> dict[str, object]:
    if not suggestion_id:
        return _unanswerable(["suggestion_id"], subject="No suggestion id was given.")
    try:
        row = suggestion_service.get_suggestion(
            session,
            business_id=business_id,
            suggestion_id=suggestion_id,
        )
    except suggestion_service.AgentSuggestionError as exc:
        raise ExplainerError(exc.message, status_code=exc.status_code, code=exc.code) from exc
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
    evidence_blob = _first_mapping(
        payload.get("evidence"),
        extra.get("evidence"),
        payload.get("facts"),
        extra,
    )
    fields = _flatten_fields(evidence_blob, payload)
    missing = _missing_core_fields(fields, kind=str(row.get("suggestion_type") or "generic"))
    trace = get_run_trace(session, business_id=business_id, run_id=str(row.get("run_id") or ""))
    packet = {
        "answerable": not missing,
        "missing": missing,
        "kind": "suggestion",
        "subject": str(payload.get("title") or payload.get("summary") or "This suggestion"),
        "target_id": row["id"],
        "run_id": row.get("run_id"),
        "suggestion_type": row.get("suggestion_type"),
        "status": row.get("status"),
        "fields": fields,
        "evidence": jsonable(evidence_blob),
        "trace": trace,
        "confidence": fields.get("confidence") or payload.get("confidence") or "medium",
        "citations": evidence_rows(fields, source="suggestion.payload"),
    }
    if missing:
        packet["answerable"] = False
    return packet


def _evidence_for_exception(
    session: Session,
    *,
    business_id: str,
    exception_id: str,
) -> dict[str, object]:
    if not exception_id:
        return _unanswerable(["exception_id"], subject="No exception id was given.")
    try:
        row = get_exception(session, business_id=business_id, exception_id=exception_id)
    except ExceptionError as exc:
        raise ExplainerError(exc.message, status_code=exc.status_code, code=exc.code) from exc
    evidence_blob = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    fields = _flatten_fields(evidence_blob, {"reason_codes": evidence_blob.get("reason_codes")})
    missing = _missing_core_fields(fields, kind="exception")
    trace = get_run_trace(session, business_id=business_id, run_id=str(row.get("run_id") or ""))
    return {
        "answerable": not missing and bool(evidence_blob),
        "missing": missing if evidence_blob else ["exception evidence"],
        "kind": "exception",
        "subject": str(row.get("title") or "This exception"),
        "target_id": row["id"],
        "run_id": row.get("run_id"),
        "exception_type": row.get("exception_type"),
        "severity": row.get("severity"),
        "fields": fields,
        "evidence": jsonable(evidence_blob),
        "trace": trace,
        "confidence": "high" if not missing else "low",
        "citations": evidence_rows(fields, source="exception.evidence"),
    }


def _evidence_for_po(
    session: Session,
    *,
    business_id: str,
    purchase_order_id: str,
) -> dict[str, object]:
    if not purchase_order_id:
        return _unanswerable(["purchase_order_id"], subject="No purchase order id was given.")
    po_id = purchase_order_id
    if not _UUID_RE.fullmatch(purchase_order_id):
        order = session.scalar(
            select(PurchaseOrder).where(
                PurchaseOrder.business_id == business_id,
                PurchaseOrder.po_number == purchase_order_id,
            )
        )
        if order is None:
            return _unanswerable(["purchase order"], subject=f"No purchase order {purchase_order_id} in this shop.")
        po_id = order.id
    try:
        raw = get_po(session, business_id=business_id, purchase_order_id=po_id)
    except PurchaseOrderError as exc:
        raise ExplainerError(exc.message, status_code=exc.status_code, code=exc.code) from exc
    related = _suggestion_for_po(session, business_id=business_id, purchase_order_id=po_id)
    evidence_blob: dict[str, object] = {
        "po_number": raw.get("po_number"),
        "status": raw.get("status"),
        "supplier_id": raw.get("supplier_id"),
        "supplier_name": raw.get("supplier_name"),
        "expected_date": None if raw.get("expected_date") is None else str(raw.get("expected_date"))[:10],
        "line_items": raw.get("line_items") or [],
    }
    fields = _flatten_fields(evidence_blob, {})
    if related is not None:
        related_fields = related.get("fields") if isinstance(related.get("fields"), dict) else {}
        fields = {**related_fields, **fields}
        if isinstance(related.get("evidence"), dict):
            evidence_blob = {**related["evidence"], **evidence_blob}
    missing: list[str] = []
    if related is None and not evidence_blob.get("line_items"):
        missing.append("suggestion evidence for this purchase order")
    trace = []
    if related and related.get("run_id"):
        trace = get_run_trace(session, business_id=business_id, run_id=str(related["run_id"]))
    return {
        "answerable": related is not None or bool(raw.get("line_items")),
        "missing": missing,
        "kind": "po",
        "subject": f"Purchase order {raw.get('po_number')}",
        "target_id": raw.get("id"),
        "run_id": related.get("run_id") if related else None,
        "fields": fields,
        "evidence": jsonable(evidence_blob),
        "trace": trace,
        "confidence": related.get("confidence") if related else "medium",
        "citations": evidence_rows(fields, source="purchase_order"),
    }


def _evidence_for_product(
    session: Session,
    *,
    business_id: str,
    product_id: str,
) -> dict[str, object]:
    try:
        listed = list_forecasts(session, business_id=business_id)
        history = get_history(session, business_id=business_id, product_id=product_id)
    except ForecastError as exc:
        raise ExplainerError(exc.message, status_code=exc.status_code, code=exc.code) from exc
    items = listed.get("items")
    match = next(
        (item for item in items if isinstance(item, dict) and item.get("product_id") == product_id),
        None,
    )
    if match is None:
        return _unanswerable(["product forecast"], subject="No forecast for that product.")
    fields = {
        "sku": match.get("sku"),
        "product_name": match.get("product_name"),
        "forecast_units": match.get("forecast_units"),
        "forecast_method": match.get("method"),
        "chosen_model": match.get("method"),
        "daily_average": match.get("daily_average"),
        "history_units": match.get("history_units"),
        "horizon_days": listed.get("horizon_days"),
        "history_days": listed.get("history_days"),
    }
    return {
        "answerable": True,
        "missing": [],
        "kind": "product",
        "subject": f"Forecast for {match.get('sku')}",
        "target_id": product_id,
        "run_id": None,
        "fields": fields,
        "evidence": jsonable({**fields, "history": history.get("items")}),
        "trace": [],
        "confidence": "medium",
        "citations": evidence_rows(fields, source="forecast"),
    }


def _latest_suggestion(session: Session, business_id: str) -> dict[str, object] | None:
    row = session.scalar(
        select(AgentSuggestion)
        .where(AgentSuggestion.business_id == business_id)
        .order_by(AgentSuggestion.created_at.desc())
    )
    if row is None:
        return None
    return suggestion_service.get_suggestion(session, business_id=business_id, suggestion_id=row.id)


def _suggestion_for_po(
    session: Session,
    *,
    business_id: str,
    purchase_order_id: str,
) -> dict[str, object] | None:
    rows = suggestion_service.list_suggestions(session, business_id=business_id)
    for row in reversed(rows):
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
        if str(payload.get("purchase_order_id") or extra.get("purchase_order_id") or "") == purchase_order_id:
            return _evidence_for_suggestion(session, business_id=business_id, suggestion_id=str(row["id"]))
    return None


def _looks_like_suggestion(session: Session, business_id: str, target_id: str) -> bool:
    row = session.scalar(
        select(AgentSuggestion).where(
            AgentSuggestion.business_id == business_id,
            AgentSuggestion.id == target_id,
        )
    )
    return row is not None


def _first_mapping(*values: object) -> dict[str, object]:
    for value in values:
        if isinstance(value, dict) and value:
            return dict(value)
        if isinstance(value, list) and value:
            merged: dict[str, object] = {}
            for item in value:
                if isinstance(item, dict):
                    merged.update(item)
            if merged:
                return merged
    return {}


def _flatten_fields(evidence: dict[str, object], payload: dict[str, object]) -> dict[str, object]:
    fields: dict[str, object] = {}
    for key in (
        "sku",
        "product_id",
        "product_name",
        "on_hand",
        "reorder_point",
        "safety_stock",
        "forecast_units",
        "forecast_method",
        "chosen_model",
        "daily_average",
        "horizon_days",
        "history_units",
        "recommended_quantity",
        "unit_cost",
        "lead_time_days",
        "reliability_score",
        "overdue_count",
        "supplier_id",
        "supplier_name",
        "days_of_cover",
        "daily_demand",
        "expected_on",
        "expected_date",
        "days_overdue",
        "po_number",
        "confidence",
    ):
        if evidence.get(key) is not None:
            fields[key] = evidence[key]
        elif payload.get(key) is not None:
            fields[key] = payload[key]
    codes = evidence.get("reason_codes") or payload.get("reason_codes")
    if isinstance(codes, list):
        fields["reason_codes"] = codes
    if payload.get("confidence") is not None:
        fields.setdefault("confidence", payload["confidence"])
    return fields


def _missing_core_fields(fields: dict[str, object], *, kind: str) -> list[str]:
    missing: list[str] = []
    if kind in {"draft_po", "suggestion"} and fields.get("recommended_quantity") is None and fields.get("on_hand") is None:
        if not fields:
            missing.append("input numbers")
    if kind == "exception" and not fields:
        missing.append("detector evidence")
    return missing


def _loader_kwargs(loader: object, target_id: str) -> dict[str, str]:
    name = getattr(loader, "__name__", "")
    if name == "_evidence_for_exception":
        return {"exception_id": target_id}
    if name == "_evidence_for_po":
        return {"purchase_order_id": target_id}
    return {"suggestion_id": target_id}


def _unanswerable(missing: list[str], *, subject: str) -> dict[str, object]:
    return {
        "answerable": False,
        "missing": missing,
        "kind": None,
        "subject": subject,
        "target_id": None,
        "run_id": None,
        "fields": {},
        "evidence": {},
        "trace": [],
        "confidence": "low",
        "citations": [],
    }


def _close_match(number: Decimal, allowed: set[Decimal]) -> bool:
    for item in allowed:
        if number == item:
            return True
        try:
            if item == number.quantize(item) or number == item.quantize(number):
                return True
        except Exception:
            continue
    return False
