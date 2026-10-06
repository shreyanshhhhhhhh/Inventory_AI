from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm.gateway import LLMGateway
from app.llm.prompts.registry import get_prompt
from app.llm.providers.base import ChatMessage
from app.llm.security import DATA_BLOCK_INSTRUCTIONS, wrap_untrusted
from app.orchestrator.intents import (
    INTENT_ALLOWLIST,
    OWNER_ONLY_INTENTS,
    parse_slash_commands,
    supported_command_list,
)
from app.orchestrator.resolve import resolve_entity_ids
from app.orchestrator.types import IntentItem, UnderstandOutput

REFUSAL_PREFIX = (
    "I can only help with inventory work in this shop: stock, forecasts, exception scans, "
    "reorder suggestions, draft purchase orders, draft supplier emails, explanations, and data quality."
)


def understand_message(
    session: Session,
    *,
    gateway: LLMGateway,
    business_id: str,
    run_id: str,
    message: str,
    history: list[dict[str, str]],
    role: str,
) -> dict[str, Any]:
    slashes = parse_slash_commands(message)
    if slashes is not None:
        unknown = [item.command for item in slashes if item.intent not in INTENT_ALLOWLIST]
        if unknown:
            return _refusal(f"I do not recognize /{unknown[0]}.")
        intents = [
            IntentItem(intent=item.intent, params=_slash_params(item.intent, item.remainder))
            for item in slashes
        ]
        return _finalize(
            session,
            business_id=business_id,
            message=message,
            history=history,
            role=role,
            intents=intents,
            confidence=1.0,
            ambiguous=False,
        )

    prompt = get_prompt("understand")
    history_blob = [{"role": row["role"], "content": row["content"]} for row in history]
    parsed = gateway.complete_structured(
        [
            ChatMessage(role="system", content=f"{prompt.template}\n{DATA_BLOCK_INSTRUCTIONS}"),
            ChatMessage(
                role="user",
                content=wrap_untrusted(
                    {"message": message, "recent_chat": history_blob},
                    label="chat",
                ),
            ),
        ],
        UnderstandOutput,
        prompt_name="understand",
        business_id=business_id,
        run_id=run_id,
    )
    allowed = [item for item in parsed.intents if item.intent in INTENT_ALLOWLIST]
    dropped_unknown = [item.intent for item in parsed.intents if item.intent not in INTENT_ALLOWLIST]
    if not allowed:
        if parsed.ambiguous and parsed.intents:
            return _clarification(parsed.intents, parsed.confidence)
        return _refusal(
            "That is outside what I can do here."
            if dropped_unknown or not parsed.intents
            else "I could not map that to a supported action."
        )
    if parsed.ambiguous or parsed.confidence < settings.orchestrator_confidence_min:
        return _clarification(allowed, parsed.confidence)
    return _finalize(
        session,
        business_id=business_id,
        message=message,
        history=history,
        role=role,
        intents=allowed,
        confidence=parsed.confidence,
        ambiguous=False,
    )


def _slash_params(intent: str, remainder: str) -> dict[str, object]:
    text = remainder.strip()
    if not text:
        return {}
    if intent == "draft_po":
        return {"supplier_name": text, "query": text}
    if intent == "draft_email":
        return _email_slash_params(text)
    return {"query": text}


def _email_slash_params(text: str) -> dict[str, object]:
    from app.services.supplier_email import EMAIL_KINDS, normalize_kind

    kind_tokens = set(EMAIL_KINDS) | {"delay", "delaynotice", "delay_notice"}
    kind: str | None = None
    name_parts: list[str] = []
    for token in text.split():
        normalized = token.lower().replace("_", "-")
        if normalized in kind_tokens or normalized.replace("-", "") == "delaynotice":
            kind = normalize_kind(normalized)
            continue
        name_parts.append(token)
    params: dict[str, object] = {}
    if name_parts:
        name = " ".join(name_parts)
        params["supplier_name"] = name
        params["query"] = name
    if kind:
        params["kind"] = kind
    return params


def _finalize(
    session: Session,
    *,
    business_id: str,
    message: str,
    history: list[dict[str, str]],
    role: str,
    intents: list[IntentItem],
    confidence: float,
    ambiguous: bool,
) -> dict[str, Any]:
    history_text = "\n".join(f"{row['role']}: {row['content']}" for row in [*history, {"role": "user", "content": message}])
    forbidden = [item for item in intents if item.intent in OWNER_ONLY_INTENTS and role != "owner"]
    allowed = [item for item in intents if not (item.intent in OWNER_ONLY_INTENTS and role != "owner")]
    if forbidden and not allowed:
        return {
            "outcome": "refuse",
            "intents": [],
            "confidence": confidence,
            "card": {
                "type": "refusal",
                "message": "Drafting purchase orders and supplier emails is owner-only.",
                "supported_commands": [item for item in supported_command_list() if item not in {"/draft-po", "/email"}],
            },
        }
    resolved: list[dict[str, Any]] = []
    for item in allowed:
        params = resolve_entity_ids(
            session,
            business_id=business_id,
            params=dict(item.params),
            history_text=history_text,
        )
        resolved.append({"intent": item.intent, "params": params})
    if ambiguous or not resolved:
        return _clarification([IntentItem(intent=row["intent"], params=row["params"]) for row in resolved], confidence)
    return {
        "outcome": "ok",
        "intents": resolved,
        "confidence": confidence,
        "forbidden": [item.intent for item in forbidden],
        "card": None,
    }


def _clarification(intents: list[IntentItem], confidence: float) -> dict[str, Any]:
    options = []
    seen: set[str] = set()
    for item in intents:
        if item.intent in seen or item.intent not in INTENT_ALLOWLIST:
            continue
        seen.add(item.intent)
        options.append({"intent": item.intent, "label": _label(item.intent)})
    if not options:
        for command in supported_command_list():
            options.append({"intent": command, "label": command})
    return {
        "outcome": "clarify",
        "intents": [],
        "confidence": confidence,
        "card": {
            "type": "clarification",
            "message": "I am not sure what you want. Pick one of these:",
            "options": options,
        },
    }


def _refusal(message: str) -> dict[str, Any]:
    return {
        "outcome": "refuse",
        "intents": [],
        "confidence": 0.0,
        "card": {
            "type": "refusal",
            "message": f"{message} {REFUSAL_PREFIX}",
            "supported_commands": supported_command_list(),
        },
    }


def _label(intent: str) -> str:
    labels = {
        "get_stock": "Show on-hand stock",
        "forecast": "Show the demand forecast",
        "scan_exceptions": "Scan for stock and order problems",
        "reorder": "Recommend reorder quantities",
        "draft_po": "Draft a purchase order suggestion",
        "draft_email": "Draft supplier emails",
        "explain": "Explain the latest figures",
        "data_quality": "Check catalog data quality",
    }
    return labels.get(intent, intent)
