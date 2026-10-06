from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRunCreate(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


class ChatRunResponse(BaseModel):
    id: str
    status: str


class ChatResumeRequest(BaseModel):
    action: Literal["run", "edit", "cancel"]
    plan: dict[str, Any] | None = None
