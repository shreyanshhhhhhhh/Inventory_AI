from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog, User


@dataclass(frozen=True)
class AuditEntryRow:
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


def list_audit_entries(
    session: Session,
    *,
    business_id: str,
    entity_type: str | None,
    entity_id: str | None,
    action: str | None,
    page: int,
    page_size: int,
) -> tuple[list[AuditEntryRow], int]:
    stmt = (
        select(AuditLog, User.full_name)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .where(AuditLog.business_id == business_id)
    )
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)

    total = int(session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = session.execute(
        stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return (
        [
            AuditEntryRow(
                id=entry.id,
                created_at=entry.created_at,
                actor_type=entry.actor_type,
                actor_user_id=entry.actor_user_id,
                actor_name=actor_name,
                action=entry.action,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                before_data=entry.before_data,
                after_data=entry.after_data,
            )
            for entry, actor_name in rows
        ],
        total,
    )
