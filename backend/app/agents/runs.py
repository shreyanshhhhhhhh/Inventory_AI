from sqlalchemy.orm import Session

from app.models import AgentRun
from app.models.types import new_id, utcnow


def start_agent_run(
    session: Session,
    *,
    business_id: str,
    agent_name: str,
    actor_user_id: str | None,
    prompt_name: str | None = None,
    prompt_version: str | None = None,
) -> AgentRun:
    run = AgentRun(
        id=new_id(),
        business_id=business_id,
        agent_name=agent_name,
        status="running",
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        actor_user_id=actor_user_id,
    )
    session.add(run)
    session.flush()
    return run


def finish_agent_run(
    session: Session,
    *,
    run: AgentRun,
    status: str,
    error_message: str | None = None,
) -> None:
    run.status = status
    run.finished_at = utcnow()
    run.error_message = error_message
    session.flush()
