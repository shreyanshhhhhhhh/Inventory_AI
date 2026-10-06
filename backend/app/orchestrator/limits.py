from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AgentRun
from app.orchestrator.errors import OrchestratorError

_rate: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def reset_limits_for_tests() -> None:
    with _lock:
        _rate.clear()


def check_user_limits(session: Session, *, user_id: str, business_id: str) -> None:
    now = time.time()
    window = 60.0
    with _lock:
        stamps = _rate[user_id]
        while stamps and now - stamps[0] > window:
            stamps.popleft()
        if len(stamps) >= settings.orchestrator_rate_limit_per_user_per_minute:
            raise OrchestratorError(
                "Too many chat runs. Wait a minute and try again.",
                code="rate_limited",
                status_code=429,
            )
        stamps.append(now)

    running = session.scalar(
        select(func.count()).select_from(AgentRun).where(
            AgentRun.business_id == business_id,
            AgentRun.actor_user_id == user_id,
            AgentRun.status.in_(("running", "awaiting_approval")),
        )
    ) or 0
    if int(running) >= settings.orchestrator_max_concurrent_runs_per_user:
        raise OrchestratorError(
            "You already have a chat run in progress.",
            code="too_many_runs",
            status_code=429,
        )


def utc_stamp() -> str:
    return datetime.now(timezone.utc).isoformat()
