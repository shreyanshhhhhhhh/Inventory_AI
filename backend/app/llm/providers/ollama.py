from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from app.core.config import Settings
from app.llm.errors import LLMError, LLMTimeoutError, RateLimitError
from app.llm.providers.base import ChatMessage, ProviderResult


class OllamaProvider:
    name = "ollama"
    supports_json_schema = True

    def __init__(self, *, model: str, timeout_seconds: float, settings: Settings) -> None:
        self._model = model
        self._timeout = timeout_seconds
        self._base_url = settings.ollama_base_url.rstrip("/")

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        prompt_name: str,
        json_schema: Mapping[str, Any] | None = None,
    ) -> ProviderResult:
        del prompt_name
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": item.role, "content": item.content} for item in messages],
            "stream": False,
        }
        if json_schema is not None:
            payload["format"] = dict(json_schema)
        try:
            response = httpx.post(
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError() from exc
        if response.status_code in {429, 503}:
            raise RateLimitError()
        if response.status_code >= 400:
            raise LLMError(
                f"Language model request failed ({response.status_code}).",
                code="llm_provider_error",
                status_code=502,
            )
        body = response.json()
        text = body.get("message", {}).get("content", "")
        return ProviderResult(
            text=str(text),
            tokens_in=int(body.get("prompt_eval_count") or 0),
            tokens_out=int(body.get("eval_count") or 0),
        )
