from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from app.llm.errors import LLMError
from app.llm.providers.base import ChatMessage, ProviderResult

_RESPONSES_PATH = Path(__file__).resolve().parent / "fake_responses.yaml"


class FakeProvider:
    name = "fake"
    supports_json_schema = False

    def __init__(self) -> None:
        payload = yaml.safe_load(_RESPONSES_PATH.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise LLMError("Fake LLM responses file is invalid.", code="llm_config")
        self._scripts: dict[str, Any] = payload
        self._attempts: dict[str, int] = {}

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        prompt_name: str,
        json_schema: Mapping[str, Any] | None = None,
    ) -> ProviderResult:
        del messages, json_schema
        script = self._scripts.get(prompt_name) or self._scripts.get("echo") or {}
        attempts = script.get("attempts")
        if isinstance(attempts, list) and attempts:
            index = self._attempts.get(prompt_name, 0)
            chosen = attempts[min(index, len(attempts) - 1)]
            self._attempts[prompt_name] = index + 1
            return ProviderResult(
                text=str(chosen.get("text", "")),
                tokens_in=int(chosen.get("tokens_in", 1)),
                tokens_out=int(chosen.get("tokens_out", 1)),
            )
        return ProviderResult(
            text=str(script.get("text", "ok")),
            tokens_in=int(script.get("tokens_in", 1)),
            tokens_out=int(script.get("tokens_out", 1)),
        )
