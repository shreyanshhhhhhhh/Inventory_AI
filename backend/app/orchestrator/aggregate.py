from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.jsonutil import jsonable
from app.llm.gateway import LLMGateway
from app.llm.prompts.registry import get_prompt
from app.llm.providers.base import ChatMessage
from app.llm.security import DATA_BLOCK_INSTRUCTIONS, wrap_untrusted
from app.orchestrator.types import SummaryOutput, TypedResult

_NUMBER = re.compile(r"(?<![A-Za-z_/])[-+]?\d+(?:\.\d+)?")


def numbers_in_text(text: str) -> list[Decimal]:
    found: list[Decimal] = []
    for match in _NUMBER.finditer(text):
        try:
            found.append(Decimal(match.group(0)))
        except InvalidOperation:
            continue
    return found


def numbers_in_results(results: dict[str, TypedResult]) -> set[Decimal]:
    blob = jsonable({key: value.model_dump() for key, value in results.items()})
    found: set[Decimal] = set()

    def walk(value: Any) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, int) and not isinstance(value, bool):
            found.add(Decimal(value))
            return
        if isinstance(value, float):
            found.add(Decimal(str(value)))
            return
        if isinstance(value, Decimal):
            found.add(value)
            return
        if isinstance(value, str):
            for item in numbers_in_text(value):
                found.add(item)
            return
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
            return
        if isinstance(value, list):
            for item in value:
                walk(item)

    walk(blob)
    return found


def summary_is_grounded(summary: str, results: dict[str, TypedResult]) -> bool:
    allowed = numbers_in_results(results)
    for number in numbers_in_text(summary):
        if number not in allowed and not _close_match(number, allowed):
            return False
    return True


def template_summary(results: dict[str, TypedResult]) -> str:
    ok = sum(1 for item in results.values() if item.status in {"ok", "not_implemented"})
    failed = sum(1 for item in results.values() if item.status == "failed")
    skipped = sum(1 for item in results.values() if item.status == "skipped")
    total = len(results)
    return (
        f"Finished {total} steps: {ok} succeeded, {failed} failed, {skipped} skipped. "
        "Placeholder agents have not been filled in yet."
    )


def write_summary(
    gateway: LLMGateway,
    *,
    business_id: str,
    run_id: str,
    results: dict[str, TypedResult],
) -> str:
    prompt = get_prompt("orchestrator_summary")
    payload = jsonable({key: value.model_dump() for key, value in results.items()})
    try:
        structured = gateway.complete_structured(
            [
                ChatMessage(role="system", content=f"{prompt.template}\n{DATA_BLOCK_INSTRUCTIONS}"),
                ChatMessage(role="user", content=wrap_untrusted(payload, label="typed_results")),
            ],
            SummaryOutput,
            prompt_name="orchestrator_summary",
            business_id=business_id,
            run_id=run_id,
        )
        text = structured.summary.strip()
    except Exception:
        return template_summary(results)
    if not text or not summary_is_grounded(text, results):
        return template_summary(results)
    return text


def _close_match(number: Decimal, allowed: set[Decimal]) -> bool:
    for item in allowed:
        if number == item:
            return True
        if number == item.quantize(number) if item == number else False:
            return True
    return False
