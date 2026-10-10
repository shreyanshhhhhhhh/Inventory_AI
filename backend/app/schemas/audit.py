from datetime import datetime

from pydantic import BaseModel


class AuditEntryResponse(BaseModel):
    id: str
    created_at: datetime
    actor_type: str
    actor_user_id: str | None
    actor_name: str | None
    action: str
    entity_type: str
    entity_id: str
    before_data: dict[str, object] | None
    after_data: dict[str, object] | None


class AuditLogResponse(BaseModel):
    items: list[AuditEntryResponse]
    total: int
    page: int
    page_size: int
