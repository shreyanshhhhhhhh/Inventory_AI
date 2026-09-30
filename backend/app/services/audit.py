from sqlalchemy.orm import Session

from app.models import AuditLog


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
