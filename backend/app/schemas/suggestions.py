from typing import Any

from pydantic import BaseModel, Field


class RejectSuggestionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class SuggestionDecisionResponse(BaseModel):
    id: str
    suggestion_type: str
    status: str
    payload: dict[str, Any]
