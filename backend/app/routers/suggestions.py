from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_owner
from app.core.errors import AppError
from app.db import get_db
from app.models import User
from app.schemas.suggestions import RejectSuggestionRequest, SuggestionDecisionResponse
from app.services.agent_suggestions import (
    AgentSuggestionError,
    approve_suggestion,
    reject_suggestion,
)

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


def _business_id(user: User) -> str:
    if user.business_id is None or user.role is None:
        raise AppError("This account is not attached to a business.", code="forbidden", status_code=403)
    return user.business_id


def _raise(exc: AgentSuggestionError) -> None:
    raise AppError(exc.message, code=exc.code, status_code=exc.status_code)


@router.post("/{suggestion_id}/approve", response_model=SuggestionDecisionResponse)
def approve_suggestion_route(
    suggestion_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
) -> SuggestionDecisionResponse:
    try:
        row = approve_suggestion(
            db,
            business_id=_business_id(user),
            actor_user_id=user.id,
            actor_role=user.role or "",
            suggestion_id=suggestion_id,
        )
    except AgentSuggestionError as exc:
        _raise(exc)
    return SuggestionDecisionResponse.model_validate(row)


@router.post("/{suggestion_id}/reject", response_model=SuggestionDecisionResponse)
def reject_suggestion_route(
    suggestion_id: str,
    body: RejectSuggestionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
) -> SuggestionDecisionResponse:
    try:
        row = reject_suggestion(
            db,
            business_id=_business_id(user),
            actor_user_id=user.id,
            actor_role=user.role or "",
            suggestion_id=suggestion_id,
            reason=body.reason,
        )
    except AgentSuggestionError as exc:
        _raise(exc)
    return SuggestionDecisionResponse.model_validate(row)
