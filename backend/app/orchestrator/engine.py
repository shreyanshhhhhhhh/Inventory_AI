from __future__ import annotations

import threading
from typing import Any, Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.jsonutil import jsonable
from app.db import SessionLocal
from app.llm.gateway import LLMGateway
from app.models import AgentRun, ConversationMessage
from app.models.types import new_id, utcnow
from app.orchestrator.errors import OrchestratorError
from app.orchestrator.events import BUS, OrchestratorEvent
from app.orchestrator.graph import OrchestratorRuntime, OrchestratorState, build_graph
from app.orchestrator.limits import check_user_limits
from app.orchestrator.plan import Plan
from app.orchestrator.registry import AgentRegistry, DEFAULT_REGISTRY
from app.services.audit import log_action

_lock = threading.Lock()
_cancel_flags: dict[str, bool] = {}
_stored_events: dict[str, list[OrchestratorEvent]] = {}


def reset_orchestrator_runtime_for_tests() -> None:
    with _lock:
        _cancel_flags.clear()
        _stored_events.clear()


def list_history(session: Session, *, business_id: str, user_id: str) -> list[dict[str, str]]:
    rows = list(
        session.scalars(
            select(ConversationMessage)
            .where(
                ConversationMessage.business_id == business_id,
                ConversationMessage.user_id == user_id,
            )
            .order_by(ConversationMessage.created_at.desc())
            .limit(settings.orchestrator_chat_history)
        )
    )
    rows.reverse()
    return [{"role": row.role, "content": row.content} for row in rows]


def get_run(
    session: Session,
    *,
    business_id: str,
    user_id: str,
    run_id: str,
) -> AgentRun:
    run = session.scalar(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.business_id == business_id,
            AgentRun.actor_user_id == user_id,
        )
    )
    if run is None:
        raise OrchestratorError("Chat run was not found.", code="not_found", status_code=404)
    return run


def start_chat_run(
    session: Session,
    *,
    business_id: str,
    user_id: str,
    role: str,
    message: str,
    gateway: LLMGateway | None = None,
    registry: AgentRegistry | None = None,
    background: bool = True,
) -> AgentRun:
    check_user_limits(session, user_id=user_id, business_id=business_id)
    history = list_history(session, business_id=business_id, user_id=user_id)
    run = AgentRun(
        id=new_id(),
        business_id=business_id,
        agent_name="orchestrator",
        status="running",
        prompt_name="understand",
        prompt_version="1",
        actor_user_id=user_id,
        input_text=message,
        events_data=[],
        cancel_requested=False,
        state_data={
            "run_id": "",
            "message": message,
            "history": history,
            "role": role,
            "business_id": business_id,
            "user_id": user_id,
        },
    )
    session.add(run)
    session.flush()
    run.state_data = {**(run.state_data or {}), "run_id": run.id}
    session.add(
        ConversationMessage(
            id=new_id(),
            business_id=business_id,
            user_id=user_id,
            role="user",
            content=message,
            run_id=run.id,
        )
    )
    log_action(
        session,
        business_id=business_id,
        actor_user_id=user_id,
        action="orchestrator.run.start",
        entity_type="agent_run",
        entity_id=run.id,
        before_data=None,
        after_data={"message": message},
    )
    session.commit()
    session.refresh(run)
    with _lock:
        _cancel_flags[run.id] = False
        _stored_events[run.id] = []
    if background:
        thread = threading.Thread(
            target=_worker,
            kwargs={
                "run_id": run.id,
                "registry": registry,
            },
            daemon=True,
        )
        thread.start()
        return run
    _execute_run(session, run=run, gateway=gateway, registry=registry)
    session.commit()
    session.refresh(run)
    return run


def resume_chat_run(
    session: Session,
    *,
    business_id: str,
    user_id: str,
    run_id: str,
    action: str,
    plan: dict[str, Any] | None = None,
    gateway: LLMGateway | None = None,
    registry: AgentRegistry | None = None,
    background: bool = True,
) -> AgentRun:
    run = get_run(session, business_id=business_id, user_id=user_id, run_id=run_id)
    if run.status != "awaiting_approval":
        raise OrchestratorError("This run is not waiting for approval.", code="conflict", status_code=409)
    if action == "cancel":
        return cancel_chat_run(session, business_id=business_id, user_id=user_id, run_id=run_id)
    if action not in {"run", "edit"}:
        raise OrchestratorError("Approval action must be run, edit, or cancel.", code="bad_request")
    state = dict(run.state_data or {})
    state["approved"] = True
    state["resume_from"] = "dispatch" if action == "run" else "approve_plan"
    if action == "edit":
        if not plan:
            raise OrchestratorError("Edited plan is required.", code="bad_request")
        state["edited_plan"] = plan
        state["resume_from"] = "approve_plan"
    run.state_data = state
    run.status = "running"
    session.commit()
    if background:
        threading.Thread(target=_worker, kwargs={"run_id": run.id, "registry": registry}, daemon=True).start()
        return run
    _execute_run(session, run=run, gateway=gateway, registry=registry)
    session.commit()
    session.refresh(run)
    return run


def cancel_chat_run(
    session: Session,
    *,
    business_id: str,
    user_id: str,
    run_id: str,
) -> AgentRun:
    run = get_run(session, business_id=business_id, user_id=user_id, run_id=run_id)
    run.cancel_requested = True
    with _lock:
        _cancel_flags[run_id] = True
    if run.status in {"awaiting_approval", "running"}:
        run.status = "cancelled"
        run.finished_at = utcnow()
        _record_event(
            session,
            run,
            OrchestratorEvent(type="cancelled", run_id=run.id, payload={}),
        )
        BUS.emit(OrchestratorEvent(type="cancelled", run_id=run.id, payload={}))
        BUS.close(run.id)
    session.commit()
    session.refresh(run)
    return run


def iter_events(run_id: str, *, replay: list[OrchestratorEvent] | None = None) -> Iterator[OrchestratorEvent]:
    stored = replay if replay is not None else list(_stored_events.get(run_id) or [])
    yield from BUS.subscribe(run_id, replay=stored)


def _worker(*, run_id: str, registry: AgentRegistry | None) -> None:
    session = SessionLocal()
    try:
        run = session.get(AgentRun, run_id)
        if run is None:
            return
        gateway = LLMGateway(session)
        _execute_run(session, run=run, gateway=gateway, registry=registry)
        session.commit()
    except Exception:
        session.rollback()
        run = session.get(AgentRun, run_id)
        if run is not None and run.status == "running":
            run.status = "failed"
            run.finished_at = utcnow()
            run.error_message = "Orchestrator run failed."
            session.commit()
            BUS.emit(
                OrchestratorEvent(
                    type="error",
                    run_id=run_id,
                    payload={"message": "Orchestrator run failed.", "code": "internal_error"},
                )
            )
        BUS.close(run_id)
    finally:
        session.close()


def _execute_run(
    session: Session,
    *,
    run: AgentRun,
    gateway: LLMGateway | None,
    registry: AgentRegistry | None,
) -> None:
    llm = gateway or LLMGateway(session)

    def is_cancelled() -> bool:
        with _lock:
            flagged = _cancel_flags.get(run.id, False)
        if flagged:
            return True
        session.expire(run, ["cancel_requested"])
        session.refresh(run, attribute_names=["cancel_requested"])
        return bool(run.cancel_requested)

    def emit(event: OrchestratorEvent) -> None:
        _record_event(session, run, event)
        BUS.emit(event)
        session.commit()

    runtime = OrchestratorRuntime(
        session,
        gateway=llm,
        registry=registry or DEFAULT_REGISTRY,
        is_cancelled=is_cancelled,
        emit=emit,
    )
    graph = build_graph(runtime)
    initial: OrchestratorState = dict(run.state_data or {})  # type: ignore[assignment]
    initial["run_id"] = run.id
    result = graph.invoke(initial)
    run.state_data = jsonable(result)
    if result.get("plan"):
        run.plan_data = result["plan"]
    outcome = str(result.get("outcome") or "")
    summary = str(result.get("summary") or result.get("reply") or "")
    cancelled_now = bool(run.cancel_requested) or _cancel_flags.get(run.id, False)
    if cancelled_now or outcome == "cancelled":
        run.status = "cancelled"
        run.finished_at = utcnow()
        BUS.close(run.id)
        return
    if outcome == "awaiting_approval":
        run.status = "awaiting_approval"
        return
    if outcome in {"clarify", "refuse", "ok"} or result.get("reply"):
        run.status = "completed"
        run.finished_at = utcnow()
        if summary:
            session.add(
                ConversationMessage(
                    id=new_id(),
                    business_id=run.business_id,
                    user_id=run.actor_user_id or "",
                    role="assistant",
                    content=summary,
                    run_id=run.id,
                )
            )
        BUS.close(run.id)
        return
    run.status = "failed"
    run.finished_at = utcnow()
    BUS.close(run.id)


def _record_event(session: Session, run: AgentRun, event: OrchestratorEvent) -> None:
    with _lock:
        _stored_events.setdefault(run.id, []).append(event)
        stored = [item.model_dump() for item in _stored_events[run.id]]
    run.events_data = stored
    if event.type == "plan":
        run.plan_data = event.payload
    session.flush()
