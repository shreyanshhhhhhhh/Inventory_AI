from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RefreshToken


def get_refresh_token_by_hash(session: Session, token_hash: str) -> RefreshToken | None:
    return session.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
