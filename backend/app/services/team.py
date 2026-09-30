from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User
from app.models.types import new_id
from app.repositories.team import count_active_owners, get_business_user, list_business_users
from app.repositories.users import get_user_by_email
from app.services.audit import log_action
from app.services.settings import SettingsError


def _user_payload(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
    }


def list_users(session: Session, *, business_id: str) -> list[dict[str, object]]:
    return [_user_payload(user) for user in list_business_users(session, business_id)]


def create_staff_user(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    full_name: str,
    email: str,
    temporary_password: str,
) -> dict[str, object]:
    if get_user_by_email(session, email) is not None:
        raise SettingsError(
            "An account with this email already exists.",
            status_code=409,
            code="conflict",
        )

    user = User(
        id=new_id(),
        business_id=business_id,
        email=email,
        password_hash=hash_password(temporary_password),
        full_name=full_name,
        role="staff",
        is_active=True,
        invited_by_user_id=actor_user_id,
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise SettingsError(
            "An account with this email already exists.",
            status_code=409,
            code="conflict",
        ) from exc

    payload = _user_payload(user)
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="user.create",
        entity_type="user",
        entity_id=user.id,
        before_data=None,
        after_data={**payload, "invited_by_user_id": actor_user_id},
    )
    session.commit()
    session.refresh(user)
    return payload


def update_user_role(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    user_id: str,
    role: str,
) -> dict[str, object]:
    user = get_business_user(session, business_id, user_id)
    if user is None:
        raise SettingsError("User not found.", status_code=404, code="not_found")

    before = _user_payload(user)
    if user.role == role:
        return before

    if user.role == "owner" and role == "staff":
        if count_active_owners(session, business_id) <= 1:
            raise SettingsError(
                "Cannot demote the last owner.",
                status_code=409,
                code="last_owner",
            )

    user.role = role
    session.flush()
    after = _user_payload(user)
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="user.role.update",
        entity_type="user",
        entity_id=user.id,
        before_data=before,
        after_data=after,
    )
    session.commit()
    session.refresh(user)
    return after
