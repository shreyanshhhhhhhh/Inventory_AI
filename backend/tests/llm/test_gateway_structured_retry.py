from pydantic import BaseModel

from app.llm.gateway import LLMGateway
from app.llm.providers.base import ChatMessage
from app.services.auth import signup


class OkModel(BaseModel):
    ok: bool


def _owner(db, *, email: str, business_name: str):
    return signup(
        db,
        full_name="Ada Owner",
        email=email,
        password="correct-horse-1",
        business_name=business_name,
    )


def test_structured_output_retries_after_invalid_json(db) -> None:
    owner = _owner(db, email="llm-retry@example.com", business_name="Retry Shop")
    gateway = LLMGateway(db)
    result = gateway.complete_structured(
        [ChatMessage(role="user", content="Return the schema.")],
        OkModel,
        prompt_name="structured_retry",
        business_id=owner.user.business_id,
    )
    assert result.ok is True
