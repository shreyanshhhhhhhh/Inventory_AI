import os

from app.llm.errors import LLMError
from app.llm.providers.fake import FakeProvider


def _forbid_live_in_tests(provider: str) -> None:
    if os.environ.get("PYTEST_CURRENT_TEST") and provider != "fake":
        raise RuntimeError(f"Live LLM provider {provider!r} cannot be constructed in tests.")


def build_provider(name: str, *, model: str, timeout_seconds: float, settings: object):
    provider = name.strip().lower()
    _forbid_live_in_tests(provider)
    if provider == "fake":
        return FakeProvider()
    if provider == "gemini":
        from app.llm.providers.gemini import GeminiProvider

        return GeminiProvider(model=model, timeout_seconds=timeout_seconds, settings=settings)
    if provider == "groq":
        from app.llm.providers.groq import GroqProvider

        return GroqProvider(model=model, timeout_seconds=timeout_seconds, settings=settings)
    if provider == "ollama":
        from app.llm.providers.ollama import OllamaProvider

        return OllamaProvider(model=model, timeout_seconds=timeout_seconds, settings=settings)
    raise LLMError(f"Unknown LLM provider '{name}'.", code="llm_config")
