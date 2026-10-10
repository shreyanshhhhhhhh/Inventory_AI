from dataclasses import asdict

from sqlalchemy.orm import Session

from app.models import AuditLog
from app.repositories import audit as audit_repo


def log_action(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    before_data: dict[str, object] | None,
    after_data: dict[str, object] | None,
) -> None:
    session.add(
        AuditLog(
            business_id=business_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_data=before_data,
            after_data=after_data,
        )
    )


write_audit = log_action


def list_audit_log(
    session: Session,
    *,
    business_id: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[dict[str, object]], int]:
    rows, total = audit_repo.list_audit_entries(
        session,
        business_id=business_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        page=page,
        page_size=page_size,
    )
    return [asdict(row) for row in rows], total
