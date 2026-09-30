from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Business


def get_business(session: Session, business_id: str) -> Business | None:
    return session.scalar(select(Business).where(Business.id == business_id))
