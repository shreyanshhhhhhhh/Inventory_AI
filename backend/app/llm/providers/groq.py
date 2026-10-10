from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from app.core.config import Settings
from app.llm.errors import LLMError, LLMTimeoutError, RateLimitError
from app.llm.providers.base import ChatMessage, ProviderResult


class GroqProvider:
    name = "groq"
    supports_json_schema = True

    def __init__(self, *, model: str, timeout_seconds: float, settings: Settings) -> None:
        if not settings.groq_api_key:
            raise LLMError("GROQ_API_KEY is not set.", code="llm_config")
        self._model = model
        self._timeout = timeout_seconds
        self._api_key = settings.groq_api_key

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
        }
        if json_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_result",
                    "schema": dict(json_schema),
                    "strict": True,
                },
            }
        try:
            response = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
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
        text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = body.get("usage", {})
        return ProviderResult(
            text=str(text),
            tokens_in=int(usage.get("prompt_tokens") or 0),
            tokens_out=int(usage.get("completion_tokens") or 0),
        )
