from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def get_user_by_id(session: Session, user_id: str) -> User | None:
    return session.scalar(select(User).where(User.id == user_id))


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email))
