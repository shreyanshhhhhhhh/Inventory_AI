from app.core.errors import AppError


class LLMError(AppError):
    def __init__(self, detail: str, *, code: str, status_code: int = 400) -> None:
        super().__init__(detail, code=code, status_code=status_code)


class LLMBudgetError(LLMError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail, code="llm_budget_exceeded", status_code=429)


class LLMTimeoutError(LLMError):
    def __init__(self, detail: str = "The language model timed out.") -> None:
        super().__init__(detail, code="llm_timeout", status_code=504)


class RateLimitError(LLMError):
    def __init__(self, detail: str = "The language model is rate limited.") -> None:
        super().__init__(detail, code="llm_rate_limited", status_code=429)


class PromptNotFoundError(LLMError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail, code="prompt_not_found", status_code=400)


class StructuredOutputError(LLMError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail, code="llm_structured_output", status_code=502)
