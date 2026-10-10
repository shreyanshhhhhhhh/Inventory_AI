from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User


def list_business_users(
    session: Session,
    business_id: str,
    *,
    include_inactive: bool = False,
) -> list[User]:
    stmt = select(User).where(User.business_id == business_id)
    if not include_inactive:
        stmt = stmt.where(User.is_active.is_(True))
    return list(
        session.scalars(stmt.order_by(User.is_active.desc(), User.full_name.asc(), User.email.asc()))
    )


def get_business_user(
    session: Session,
    business_id: str,
    user_id: str,
    *,
    active_only: bool = True,
) -> User | None:
    stmt = select(User).where(User.business_id == business_id, User.id == user_id)
    if active_only:
        stmt = stmt.where(User.is_active.is_(True))
    return session.scalar(stmt)


def count_active_owners(session: Session, business_id: str) -> int:
    total = session.scalar(
        select(func.count())
        .select_from(User)
        .where(
            User.business_id == business_id,
            User.role == "owner",
            User.is_active.is_(True),
        )
    )
    return int(total or 0)
