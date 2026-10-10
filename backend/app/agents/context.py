from dataclasses import dataclass

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class AgentContext:
    session: Session
    business_id: str
    user_id: str
    role: str
    run_id: str | None = None
