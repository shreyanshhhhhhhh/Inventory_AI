from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings as default_settings
from app.core.jsonutil import jsonable
from app.llm.errors import LLMBudgetError, RateLimitError, StructuredOutputError
from app.llm.prompts.registry import get_prompt
from app.llm.providers.base import ChatMessage, LLMProvider
from app.llm.providers.factory import build_provider
from app.models import AgentStep, LlmUsageCounter
from app.models.types import new_id, utcnow

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class CompletionResult:
    text: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    prompt_name: str
    prompt_version: str
    provider: str
    step_id: str | None


class LLMGateway:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or default_settings
        self._provider = provider or build_provider(
            self._settings.llm_provider,
            model=self._settings.llm_model,
            timeout_seconds=self._settings.llm_timeout_seconds,
            settings=self._settings,
        )

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        prompt_name: str,
        business_id: str,
        run_id: str | None = None,
    ) -> CompletionResult:
        return self._call(messages, prompt_name=prompt_name, business_id=business_id, run_id=run_id)

    def complete_structured(
        self,
        messages: list[ChatMessage],
        model: type[T],
        *,
        prompt_name: str,
        business_id: str,
        run_id: str | None = None,
    ) -> T:
        schema = model.model_json_schema()
        working = list(messages)
        last_error: str | None = None
        for attempt in range(3):
            if last_error is not None:
                working = [
                    *messages,
                    ChatMessage(
                        role="user",
                        content=(
                            "The previous JSON did not match the schema. "
                            f"Validation error: {last_error}. Return valid JSON only."
                        ),
                    ),
                ]
            use_schema = self._provider.supports_json_schema
            result = self._call(
                working,
                prompt_name=prompt_name,
                business_id=business_id,
                run_id=run_id,
                json_schema=schema if use_schema else None,
            )
            try:
                payload = _parse_json(result.text)
                return model.model_validate(payload)
            except (ValueError, ValidationError) as exc:
                last_error = str(exc)
                if attempt >= 2:
                    raise StructuredOutputError(
                        "The language model did not return valid structured output."
                    ) from exc
        raise StructuredOutputError("The language model did not return valid structured output.")

    def _call(
        self,
        messages: list[ChatMessage],
        *,
        prompt_name: str,
        business_id: str,
        run_id: str | None,
        json_schema: dict[str, object] | None = None,
    ) -> CompletionResult:
        prompt = get_prompt(prompt_name)
        self._require_budget(business_id)
        started = time.perf_counter()
        result = self._complete_with_retry(messages, prompt_name=prompt_name, json_schema=json_schema)
        latency_ms = int((time.perf_counter() - started) * 1000)
        self._record_usage(business_id, result.tokens_in + result.tokens_out)
        step_id = self._log_step(
            business_id=business_id,
            run_id=run_id,
            prompt_name=prompt.name,
            prompt_version=prompt.version,
            messages=messages,
            text=result.text,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            duration_ms=latency_ms,
        )
        logger.info(
            "llm_call provider=%s prompt=%s version=%s business_id=%s latency_ms=%s tokens_in=%s tokens_out=%s",
            self._provider.name,
            prompt.name,
            prompt.version,
            business_id,
            latency_ms,
            result.tokens_in,
            result.tokens_out,
        )
        return CompletionResult(
            text=result.text,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            latency_ms=latency_ms,
            prompt_name=prompt.name,
            prompt_version=prompt.version,
            provider=self._provider.name,
            step_id=step_id,
        )

    def _complete_with_retry(
        self,
        messages: list[ChatMessage],
        *,
        prompt_name: str,
        json_schema: dict[str, object] | None,
    ):
        attempts = max(1, self._settings.llm_max_retries)
        delay = 0.25
        last_error: Exception | None = None
        for index in range(attempts):
            try:
                return self._provider.complete(
                    messages,
                    prompt_name=prompt_name,
                    json_schema=json_schema,
                )
            except RateLimitError as exc:
                last_error = exc
                if index >= attempts - 1:
                    raise
                time.sleep(delay)
                delay *= 2
        assert last_error is not None
        raise last_error

    def _require_budget(self, business_id: str) -> None:
        counter = self._counter(business_id)
        request_cap = self._settings.llm_budget_requests_per_business_per_day
        token_cap = self._settings.llm_budget_tokens_per_business_per_day
        if counter.request_count >= request_cap:
            raise LLMBudgetError(
                f"This business has used its daily language-model request budget ({request_cap})."
            )
        if counter.token_count >= token_cap:
            raise LLMBudgetError(
                f"This business has used its daily language-model token budget ({token_cap})."
            )

    def _record_usage(self, business_id: str, tokens: int) -> None:
        counter = self._counter(business_id)
        counter.request_count += 1
        counter.token_count += tokens
        self._session.flush()

    def _counter(self, business_id: str) -> LlmUsageCounter:
        today = utcnow().date()
        row = self._session.scalar(
            select(LlmUsageCounter).where(
                LlmUsageCounter.business_id == business_id,
                LlmUsageCounter.usage_date == today,
            )
        )
        if row is None:
            row = LlmUsageCounter(
                id=new_id(),
                business_id=business_id,
                usage_date=today,
                request_count=0,
                token_count=0,
            )
            self._session.add(row)
            self._session.flush()
        return row

    def _log_step(
        self,
        *,
        business_id: str,
        run_id: str | None,
        prompt_name: str,
        prompt_version: str,
        messages: list[ChatMessage],
        text: str,
        tokens_in: int,
        tokens_out: int,
        duration_ms: int,
    ) -> str | None:
        if run_id is None:
            return None
        step = AgentStep(
            id=new_id(),
            run_id=run_id,
            business_id=business_id,
            step_kind="llm",
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            input_data=jsonable({"messages": [{"role": item.role, "content": item.content} for item in messages]}),
            output_data=jsonable({"text": text}),
            duration_ms=duration_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
        self._session.add(step)
        self._session.flush()
        return step.id


def _parse_json(text: str) -> object:
    stripped = text.strip()
    fenced = _JSON_FENCE.search(stripped)
    if fenced:
        stripped = fenced.group(1).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Response was not valid JSON: {exc}") from exc
