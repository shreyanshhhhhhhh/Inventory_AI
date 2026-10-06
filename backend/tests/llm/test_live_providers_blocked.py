import pytest

from app.llm.providers.factory import build_provider


def test_live_providers_cannot_be_constructed_during_pytest() -> None:
    with pytest.raises(RuntimeError, match="cannot be constructed in tests"):
        build_provider("gemini", model="x", timeout_seconds=1, settings=None)
    with pytest.raises(RuntimeError, match="cannot be constructed in tests"):
        build_provider("groq", model="x", timeout_seconds=1, settings=None)
    with pytest.raises(RuntimeError, match="cannot be constructed in tests"):
        build_provider("ollama", model="x", timeout_seconds=1, settings=None)
