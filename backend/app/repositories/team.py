from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User


def list_business_users(session: Session, business_id: str) -> list[User]:
    return list(
        session.scalars(
            select(User)
            .where(
                User.business_id == business_id,
                User.is_active.is_(True),
            )
            .order_by(User.full_name.asc(), User.email.asc())
        )
    )


def get_business_user(session: Session, business_id: str, user_id: str) -> User | None:
    return session.scalar(
        select(User).where(
            User.business_id == business_id,
            User.id == user_id,
            User.is_active.is_(True),
        )
    )


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
