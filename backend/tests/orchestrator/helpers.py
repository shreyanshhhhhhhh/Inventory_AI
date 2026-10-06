from __future__ import annotations

from sqlalchemy.orm import Session

from app.llm.gateway import LLMGateway
from app.models import AgentRun
from app.orchestrator.engine import start_chat_run
from app.orchestrator.events import OrchestratorEvent
from app.services.auth import signup


def owner(db: Session, email: str, shop: str):
    return signup(
        db,
        full_name="Ada Owner",
        email=email,
        password="correct-horse-1",
        business_name=shop,
    )


def run_chat(db: Session, signed, message: str, *, role: str = "owner") -> AgentRun:
    gateway = LLMGateway(db)
    return start_chat_run(
        db,
        business_id=signed.user.business_id,
        user_id=signed.user.id,
        role=role,
        message=message,
        gateway=gateway,
        background=False,
    )


def event_types(run: AgentRun) -> list[str]:
    return [str(item["type"]) for item in (run.events_data or []) if isinstance(item, dict)]


def events_of(run: AgentRun, event_type: str) -> list[OrchestratorEvent]:
    found: list[OrchestratorEvent] = []
    for item in run.events_data or []:
        if not isinstance(item, dict):
            continue
        event = OrchestratorEvent.model_validate(item)
        if event.type == event_type:
            found.append(event)
    return found
