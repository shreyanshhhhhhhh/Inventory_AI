import pytest

from app.core.config import Settings
from app.llm.errors import LLMBudgetError
from app.llm.gateway import LLMGateway
from app.llm.providers.base import ChatMessage
from app.services.auth import signup


def test_budget_enforcement_blocks_second_request(db) -> None:
    owner = signup(
        db,
        full_name="Ada Owner",
        email="llm-budget@example.com",
        password="correct-horse-1",
        business_name="Budget Shop",
    )
    settings = Settings(
        jwt_secret="test-jwt-secret-not-for-production",
        llm_provider="fake",
        llm_budget_requests_per_business_per_day=1,
        llm_budget_tokens_per_business_per_day=100000,
    )
    gateway = LLMGateway(db, settings=settings)
    first = gateway.complete(
        [ChatMessage(role="user", content="hello")],
        prompt_name="echo",
        business_id=owner.user.business_id,
    )
    assert first.prompt_name == "echo"
    assert first.prompt_version == "1"
    with pytest.raises(LLMBudgetError) as exc:
        gateway.complete(
            [ChatMessage(role="user", content="again")],
            prompt_name="echo",
            business_id=owner.user.business_id,
        )
    assert exc.value.code == "llm_budget_exceeded"
    assert "request budget" in exc.value.detail
