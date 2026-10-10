from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import RefreshToken, User
from app.models.types import new_id, utcnow
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


def list_users(
    session: Session,
    *,
    business_id: str,
    include_inactive: bool = True,
) -> list[dict[str, object]]:
    return [
        _user_payload(user)
        for user in list_business_users(session, business_id, include_inactive=include_inactive)
    ]


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
    """Change a user's role. A business has exactly one owner, so promoting a staff member
    to owner transfers ownership and demotes the acting owner to staff."""
    user = get_business_user(session, business_id, user_id)
    if user is None:
        raise SettingsError("User not found.", status_code=404, code="not_found")

    before = _user_payload(user)
    if user.role == role:
        return before

    if user.role == "owner" and role == "staff":
        if count_active_owners(session, business_id) <= 1:
            raise SettingsError(
                "Cannot demote the last owner. Make another user the owner instead.",
                status_code=409,
                code="last_owner",
            )

    previous_owner: User | None = None
    if role == "owner":
        previous_owner = get_business_user(session, business_id, actor_user_id)
        if previous_owner is None or previous_owner.role != "owner":
            raise SettingsError("Only the owner can transfer ownership.", status_code=403, code="forbidden")
        previous_owner_before = _user_payload(previous_owner)
        previous_owner.role = "staff"

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
    if previous_owner is not None:
        log_action(
            session,
            business_id=business_id,
            actor_user_id=actor_user_id,
            action="user.role.update",
            entity_type="user",
            entity_id=previous_owner.id,
            before_data=previous_owner_before,
            after_data=_user_payload(previous_owner),
        )
    session.commit()
    session.refresh(user)
    return after


def set_user_active(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    user_id: str,
    is_active: bool,
) -> dict[str, object]:
    """Deactivate or reactivate a team member. Users are never deleted, so their ledger
    and audit rows stay attributable."""
    user = get_business_user(session, business_id, user_id, active_only=False)
    if user is None:
        raise SettingsError("User not found.", status_code=404, code="not_found")
    if user.id == actor_user_id:
        raise SettingsError("You cannot deactivate your own account.", status_code=409, code="conflict")
    if user.role == "owner" and not is_active:
        raise SettingsError(
            "The owner cannot be deactivated. Transfer ownership first.",
            status_code=409,
            code="last_owner",
        )

    before = _user_payload(user)
    if user.is_active == is_active:
        return before
    user.is_active = is_active
    if not is_active:
        session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
    session.flush()
    after = _user_payload(user)
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="user.activate" if is_active else "user.deactivate",
        entity_type="user",
        entity_id=user.id,
        before_data=before,
        after_data=after,
    )
    session.commit()
    session.refresh(user)
    return after
