"""Supplier email templates, fact packing, and number/date grounding. No LLM arithmetic."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

EMAIL_KINDS = ("order", "chase", "expedite", "delay-notice")

_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
_INJECTION_MARKERS = (
    "ignore instructions",
    "ignore previous",
    "system prompt",
    "<<data>>",
    "<</data>>",
    "call create_",
    "draft_po",
    "hack_the_ledger",
)

_SUBJECTS = {
    "order": "Purchase order {po_number}",
    "chase": "Status of purchase order {po_number}",
    "expedite": "Please expedite purchase order {po_number}",
    "delay-notice": "Delay notice for purchase order {po_number}",
}

_ASK_DEFAULTS = {
    "order": "Please confirm you can fulfill this order on the expected date.",
    "chase": "Please reply with the current status and a confirmed date.",
    "expedite": "Please ship as soon as you can and confirm the new date.",
    "delay-notice": "Please confirm the delay and the new expected date.",
}

_TEMPLATE = """{greeting}

{ask_intro}
{lines}
{schedule}

{ask}

{closing}
""".strip()


def normalize_kind(value: str | None) -> str:
    raw = (value or "").strip().lower().replace("_", "-").replace(" ", "-")
    if raw in {"delay", "delaynotice"}:
        return "delay-notice"
    if raw in EMAIL_KINDS:
        return raw
    return "chase"


def facts_from_po(
    *,
    supplier: dict[str, object],
    po: dict[str, object] | None,
    kind: str,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    lines: list[dict[str, str]] = []
    quantities: list[str] = []
    dates: list[str] = []
    po_numbers: list[str] = []
    if po is not None:
        po_number = str(po.get("po_number") or "")
        if po_number:
            po_numbers.append(po_number)
        expected = po.get("expected_date")
        if expected is not None:
            dates.append(_as_date_text(expected))
        raw_lines = po.get("line_items") or []
        if isinstance(raw_lines, list):
            for line in raw_lines:
                if not isinstance(line, dict):
                    continue
                qty = _qty_text(line.get("quantity") or line.get("quantity_ordered"))
                name = str(line.get("product_name") or line.get("product_id") or "item")
                lines.append({"product_name": name, "quantity": qty})
                if qty:
                    quantities.append(qty)
    payload = {
        "kind": kind,
        "supplier_id": str(supplier.get("id") or supplier.get("supplier_id") or ""),
        "supplier_name": str(supplier.get("name") or supplier.get("supplier_name") or ""),
        "to_email": str(supplier.get("email") or ""),
        "po_id": None if po is None else str(po.get("id") or ""),
        "po_number": po_numbers[0] if po_numbers else "",
        "expected_date": dates[0] if dates else "",
        "lines": lines,
        "quantities": quantities,
        "dates": dates,
        "po_numbers": po_numbers,
        "delay_days": None,
    }
    if extra:
        delay = extra.get("delay_days")
        if delay is not None:
            payload["delay_days"] = str(delay)
        exception_title = extra.get("exception_title")
        if exception_title:
            payload["exception_title"] = str(exception_title)
    return payload


def render_template(
    facts: dict[str, object],
    *,
    greeting: str = "",
    ask: str = "",
    closing: str = "",
) -> tuple[str, str]:
    kind = normalize_kind(str(facts.get("kind") or "chase"))
    po_number = str(facts.get("po_number") or "your open order")
    supplier_name = str(facts.get("supplier_name") or "there")
    expected = str(facts.get("expected_date") or "not set")
    delay = facts.get("delay_days")
    lines = _format_lines(facts)
    greeting_text = greeting.strip() or f"Hello {supplier_name},"
    ask_text = ask.strip() or _ASK_DEFAULTS[kind]
    closing_text = closing.strip() or "Thank you,"
    intros = {
        "order": "Please find the purchase details below.",
        "chase": "We are checking on this order.",
        "expedite": "We need this order sooner if you can.",
        "delay-notice": "We need to record a delay on this order.",
    }
    schedule = f"Purchase order: {po_number}\nExpected date: {expected}"
    if delay:
        schedule += f"\nDelay days: {delay}"
    body = _TEMPLATE.format(
        greeting=greeting_text,
        ask_intro=intros[kind],
        lines=lines,
        schedule=schedule,
        ask=ask_text,
        closing=closing_text,
    )
    subject = _SUBJECTS[kind].format(po_number=po_number)
    return subject, body + "\n"


def draft_is_grounded(subject: str, body: str, facts: dict[str, object]) -> bool:
    allowed_dates = {str(item) for item in facts.get("dates") or [] if item}
    expected = str(facts.get("expected_date") or "")
    if expected:
        allowed_dates.add(expected)
    allowed_pos = {str(item).lower() for item in facts.get("po_numbers") or [] if item}
    po_number = str(facts.get("po_number") or "")
    if po_number:
        allowed_pos.add(po_number.lower())
    allowed_numbers = {_canon_number(item) for item in facts.get("quantities") or []}
    delay = facts.get("delay_days")
    if delay is not None:
        allowed_numbers.add(_canon_number(delay))
    blob = f"{subject}\n{body}"
    for found in _DATE_RE.findall(blob):
        if found not in allowed_dates:
            return False
    remainder = _DATE_RE.sub(" ", blob)
    for token in allowed_pos:
        remainder = re.sub(re.escape(token), " ", remainder, flags=re.IGNORECASE)
    for found in _NUMBER_RE.findall(remainder):
        if _canon_number(found) not in allowed_numbers:
            return False
    return True


def looks_like_injection(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _INJECTION_MARKERS)


def parse_reply_fields(text: str) -> dict[str, object]:
    """Deterministic fallback extractor. Never follows instructions in the text."""
    if looks_like_injection(text):
        return {
            "confirmed_date": None,
            "quantity_confirmed": None,
            "delay_days": None,
            "price_change": None,
            "ignored_injection": True,
        }
    dates = _DATE_RE.findall(text)
    delay = None
    delay_match = re.search(r"delay(?:ed)?\s+(\d+)\s+day", text, flags=re.IGNORECASE)
    if delay_match:
        delay = int(delay_match.group(1))
    qty = None
    qty_match = re.search(r"(?:confirm(?:ed)?|quantity)\s+(\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    if qty_match:
        qty = qty_match.group(1)
    price = None
    price_match = re.search(r"(?:price|cost)\s+(?:change(?:d)?\s+)?(-?\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    if price_match:
        price = price_match.group(1)
    return {
        "confirmed_date": dates[0] if dates else None,
        "quantity_confirmed": qty,
        "delay_days": delay,
        "price_change": price,
        "ignored_injection": False,
    }


def _format_lines(facts: dict[str, object]) -> str:
    raw = facts.get("lines")
    if not isinstance(raw, list) or not raw:
        return "Lines: none on file."
    parts = []
    for line in raw:
        if not isinstance(line, dict):
            continue
        parts.append(f"- {line.get('product_name')}: {line.get('quantity')}")
    return "Lines:\n" + "\n".join(parts) if parts else "Lines: none on file."


def _qty_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value, "f")
    text = str(value)
    try:
        return format(Decimal(text), "f")
    except Exception:
        return text


def _canon_number(value: object) -> str:
    try:
        return format(Decimal(str(value)), "f")
    except Exception:
        return str(value)


def _as_date_text(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    match = _DATE_RE.search(text)
    return match.group(0) if match else text[:10]
