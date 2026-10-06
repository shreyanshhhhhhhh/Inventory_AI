from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ProviderResult:
    text: str
    tokens_in: int
    tokens_out: int


class LLMProvider(Protocol):
    name: str
    supports_json_schema: bool

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        prompt_name: str,
        json_schema: Mapping[str, Any] | None = None,
    ) -> ProviderResult:
        ...
