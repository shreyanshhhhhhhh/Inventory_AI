from __future__ import annotations

import json
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Iterator

from pydantic import BaseModel, ConfigDict, Field

EVENT_TYPES = (
    "thinking",
    "plan",
    "step_started",
    "step_progress",
    "step_done",
    "step_failed",
    "token",
    "card",
    "awaiting_approval",
    "done",
    "error",
    "cancelled",
)


class OrchestratorEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    run_id: str
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: dict[str, Any] = Field(default_factory=dict)

    def as_sse(self) -> str:
        body = {"run_id": self.run_id, "ts": self.ts, **self.payload}
        return f"event: {self.type}\ndata: {json.dumps(body)}\n\n"


_SENTINEL = object()


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queues: dict[str, deque[OrchestratorEvent | object]] = defaultdict(deque)
        self._waiters: dict[str, threading.Event] = {}
        self._closed: set[str] = set()

    def emit(self, event: OrchestratorEvent) -> None:
        with self._lock:
            self._queues[event.run_id].append(event)
            waiter = self._waiters.get(event.run_id)
            if waiter is not None:
                waiter.set()

    def close(self, run_id: str) -> None:
        with self._lock:
            self._closed.add(run_id)
            self._queues[run_id].append(_SENTINEL)
            waiter = self._waiters.get(run_id)
            if waiter is not None:
                waiter.set()

    def subscribe(self, run_id: str, *, replay: list[OrchestratorEvent] | None = None) -> Iterator[OrchestratorEvent]:
        if replay:
            yield from replay
        while True:
            event: OrchestratorEvent | object | None = None
            with self._lock:
                queue = self._queues[run_id]
                if queue:
                    event = queue.popleft()
                elif run_id in self._closed:
                    return
                else:
                    waiter = self._waiters.get(run_id)
                    if waiter is None or waiter.is_set():
                        waiter = threading.Event()
                        self._waiters[run_id] = waiter
            if event is _SENTINEL:
                return
            if isinstance(event, OrchestratorEvent):
                yield event
                continue
            waiter.wait(timeout=0.25)

    def snapshot(self, run_id: str) -> list[OrchestratorEvent]:
        with self._lock:
            return [item for item in self._queues[run_id] if isinstance(item, OrchestratorEvent)]


BUS = EventBus()
