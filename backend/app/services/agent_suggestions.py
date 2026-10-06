from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.jsonutil import jsonable
from app.models import AgentSuggestion
from app.models.types import new_id
from app.services.audit import log_action

_TYPES = {"generic", "draft_po", "draft_email"}


class AgentSuggestionError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, code: str = "bad_request") -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


def create_suggestion(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    run_id: str,
    suggestion_type: str,
    payload: dict[str, object],
) -> dict[str, object]:
    if suggestion_type not in _TYPES:
        raise AgentSuggestionError("Unknown suggestion type.")
    suggestion = AgentSuggestion(
        id=new_id(),
        business_id=business_id,
        run_id=run_id,
        suggestion_type=suggestion_type,
        status="pending",
        payload=jsonable(payload),
    )
    session.add(suggestion)
    session.flush()
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="agent.suggestion.create",
        entity_type="agent_suggestion",
        entity_id=suggestion.id,
        before_data=None,
        after_data={
            "suggestion_type": suggestion.suggestion_type,
            "run_id": run_id,
        },
    )
    return _payload(suggestion)


def list_suggestions(
    session: Session,
    *,
    business_id: str,
    run_id: str | None = None,
) -> list[dict[str, object]]:
    from sqlalchemy import select

    query = select(AgentSuggestion).where(AgentSuggestion.business_id == business_id)
    if run_id is not None:
        query = query.where(AgentSuggestion.run_id == run_id)
    rows = session.scalars(query.order_by(AgentSuggestion.created_at.asc())).all()
    return [_payload(row) for row in rows]


def _payload(suggestion: AgentSuggestion) -> dict[str, object]:
    return {
        "id": suggestion.id,
        "business_id": suggestion.business_id,
        "run_id": suggestion.run_id,
        "suggestion_type": suggestion.suggestion_type,
        "status": suggestion.status,
        "payload": suggestion.payload,
        "created_at": suggestion.created_at,
    }
