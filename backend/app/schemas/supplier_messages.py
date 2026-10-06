from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SupplierMessageResponse(BaseModel):
    id: str
    business_id: str
    supplier_id: str
    supplier_name: str | None = None
    po_id: str | None = None
    kind: str
    subject: str
    body: str
    status: str
    created_by: str
    approved_by: str | None = None
    sent_at: datetime | None = None
    thread_id: str
    suggestion_id: str | None = None
    to_email: str | None = None
    facts: dict[str, Any] | None = None
    used_template: bool | None = None


class SupplierMessageEditRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1)


class SupplierMessageSendRequest(BaseModel):
    subject: str | None = Field(default=None, max_length=240)
    body: str | None = None


class SupplierMessageRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class EmailSenderStatusResponse(BaseModel):
    mode: Literal["console", "smtp"]
    console_mode: bool
    banner: str | None = None


class SupplierReplyCreateRequest(BaseModel):
    body: str = Field(min_length=1)
    message_id: str | None = None
    thread_id: str | None = None
    business_id: str | None = None


class SupplierReplyResponse(BaseModel):
    id: str
    message_id: str
    received_at: datetime
    parsed: dict[str, Any]
    suggestion_id: str | None = None
