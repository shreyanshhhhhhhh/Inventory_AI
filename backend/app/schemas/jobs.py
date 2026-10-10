from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class ExceptionScanJobRequest(BaseModel):
    business_id: str | None = None
    force: bool = False


class ExceptionScanJobResponse(BaseModel):
    ran: int
    skipped: int
    businesses: list[dict[str, Any]] = Field(default_factory=list)
    ran_on: date
