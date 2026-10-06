from __future__ import annotations

from dataclasses import dataclass

OWNER_ONLY_INTENTS = frozenset({"draft_po", "draft_email"})
WRITE_INTENTS = frozenset({"draft_po", "draft_email"})

INTENT_ALLOWLIST = frozenset(
    {
        "get_stock",
        "forecast",
        "scan_exceptions",
        "reorder",
        "draft_po",
        "draft_email",
        "explain",
        "data_quality",
    }
)


@dataclass(frozen=True)
class SlashCommand:
    command: str
    intent: str
    remainder: str


SLASH_COMMANDS: dict[str, str] = {
    "stock": "get_stock",
    "forecast": "forecast",
    "scan": "scan_exceptions",
    "exceptions": "scan_exceptions",
    "reorder": "reorder",
    "draft-po": "draft_po",
    "po": "draft_po",
    "email": "draft_email",
    "explain": "explain",
    "quality": "data_quality",
}


def supported_command_list() -> list[str]:
    return [
        "/stock",
        "/forecast",
        "/scan",
        "/reorder",
        "/draft-po",
        "/email",
        "/explain",
        "/quality",
    ]


def parse_slash_commands(message: str) -> list[SlashCommand] | None:
    stripped = message.strip()
    if not stripped.startswith("/"):
        return None
    found: list[SlashCommand] = []
    parts = stripped.split()
    buffer_cmd: str | None = None
    remainder_parts: list[str] = []
    for token in parts:
        if token.startswith("/") and len(token) > 1:
            if buffer_cmd is not None:
                found.append(
                    SlashCommand(
                        command=buffer_cmd,
                        intent=SLASH_COMMANDS.get(buffer_cmd, ""),
                        remainder=" ".join(remainder_parts).strip(),
                    )
                )
            raw = token[1:].lower()
            buffer_cmd = raw
            remainder_parts = []
        elif buffer_cmd is not None:
            remainder_parts.append(token)
    if buffer_cmd is not None:
        found.append(
            SlashCommand(
                command=buffer_cmd,
                intent=SLASH_COMMANDS.get(buffer_cmd, ""),
                remainder=" ".join(remainder_parts).strip(),
            )
        )
    return found or None
