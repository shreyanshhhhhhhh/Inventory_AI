from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from app.core.config import Settings
from app.llm.errors import LLMError, LLMTimeoutError, RateLimitError
from app.llm.providers.base import ChatMessage, ProviderResult


def _raise_http(status_code: int, body: str) -> None:
    if status_code in {429, 503}:
        raise RateLimitError()
    raise LLMError(
        f"Language model request failed ({status_code}): {body[:200]}",
        code="llm_provider_error",
        status_code=502,
    )


class GeminiProvider:
    name = "gemini"
    supports_json_schema = True

    def __init__(self, *, model: str, timeout_seconds: float, settings: Settings) -> None:
        if not settings.gemini_api_key:
            raise LLMError("GEMINI_API_KEY is not set.", code="llm_config")
        self._model = model
        self._timeout = timeout_seconds
        self._api_key = settings.gemini_api_key

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        prompt_name: str,
        json_schema: Mapping[str, Any] | None = None,
    ) -> ProviderResult:
        del prompt_name
        system_parts = [item.content for item in messages if item.role == "system"]
        contents = []
        for item in messages:
            if item.role == "system":
                continue
            role = "model" if item.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": item.content}]})
        payload: dict[str, Any] = {"contents": contents}
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        generation: dict[str, Any] = {}
        if json_schema is not None:
            generation["responseMimeType"] = "application/json"
            generation["responseSchema"] = dict(json_schema)
        if generation:
            payload["generationConfig"] = generation
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:generateContent"
        )
        try:
            response = httpx.post(
                url,
                params={"key": self._api_key},
                json=payload,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError() from exc
        if response.status_code >= 400:
            _raise_http(response.status_code, response.text)
        body = response.json()
        text = (
            body.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        usage = body.get("usageMetadata", {})
        return ProviderResult(
            text=str(text),
            tokens_in=int(usage.get("promptTokenCount") or 0),
            tokens_out=int(usage.get("candidatesTokenCount") or 0),
        )
