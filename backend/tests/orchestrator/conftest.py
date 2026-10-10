from app.llm.prompts.registry import load_all
from app.orchestrator.engine import reset_orchestrator_runtime_for_tests
from app.orchestrator.limits import reset_limits_for_tests

load_all.cache_clear()


def pytest_runtest_setup() -> None:
    reset_limits_for_tests()
    reset_orchestrator_runtime_for_tests()
