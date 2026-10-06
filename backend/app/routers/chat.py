from collections.abc import Iterator
import json
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.errors import AppError
from app.db import SessionLocal, get_db
from app.models import AgentRun, User
from app.orchestrator.engine import cancel_chat_run, get_run, resume_chat_run, start_chat_run
from app.orchestrator.errors import OrchestratorError
from app.orchestrator.events import OrchestratorEvent
from app.schemas.chat import ChatResumeRequest, ChatRunCreate, ChatRunResponse

router = APIRouter(prefix="/chat", tags=["chat"])


def _require_business(user: User) -> str:
    if user.business_id is None or user.role is None:
        raise HTTPException(status_code=403, detail="This account is not attached to a business.")
    return user.business_id


def _raise(exc: OrchestratorError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"detail": exc.detail, "code": exc.code},
    ) from exc


@router.post("/runs", response_model=ChatRunResponse, status_code=202)
def start_run_route(
    payload: ChatRunCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatRunResponse:
    business_id = _require_business(user)
    try:
        run = start_chat_run(
            db,
            business_id=business_id,
            user_id=user.id,
            role=str(user.role),
            message=payload.message,
            background=True,
        )
    except OrchestratorError as exc:
        _raise(exc)
        raise
    return ChatRunResponse(id=run.id, status=run.status)


@router.post("/runs/{run_id}/cancel", response_model=ChatRunResponse)
def cancel_run_route(
    run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatRunResponse:
    business_id = _require_business(user)
    try:
        run = cancel_chat_run(db, business_id=business_id, user_id=user.id, run_id=run_id)
    except OrchestratorError as exc:
        _raise(exc)
        raise
    return ChatRunResponse(id=run.id, status=run.status)


@router.post("/runs/{run_id}/resume", response_model=ChatRunResponse)
def resume_run_route(
    run_id: str,
    payload: ChatResumeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatRunResponse:
    business_id = _require_business(user)
    try:
        run = resume_chat_run(
            db,
            business_id=business_id,
            user_id=user.id,
            run_id=run_id,
            action=payload.action,
            plan=payload.plan,
            background=True,
        )
    except OrchestratorError as exc:
        _raise(exc)
        raise
    except AppError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.detail, "code": exc.code},
        ) from exc
    return ChatRunResponse(id=run.id, status=run.status)


@router.get("/runs/{run_id}/events")
def stream_run_events(
    run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    business_id = _require_business(user)
    try:
        get_run(db, business_id=business_id, user_id=user.id, run_id=run_id)
    except OrchestratorError as exc:
        _raise(exc)
        raise

    def generate() -> Iterator[str]:
        seen = 0
        while True:
            session = SessionLocal()
            try:
                run = session.get(AgentRun, run_id)
                if run is None or run.business_id != business_id or run.actor_user_id != user.id:
                    yield _sse("error", {"message": "Chat run was not found.", "code": "not_found"})
                    return
                events = list(run.events_data or [])
                for raw in events[seen:]:
                    event = OrchestratorEvent.model_validate(raw)
                    yield event.as_sse()
                    seen += 1
                if run.status not in {"running", "awaiting_approval"}:
                    return
            finally:
                session.close()
            time.sleep(0.05)

    return StreamingResponse(generate(), media_type="text/event-stream")


def _sse(event_type: str, payload: dict[str, object]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
