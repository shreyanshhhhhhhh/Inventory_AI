from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Callable

from app.agents.context import AgentContext
from app.db import SessionLocal
from app.orchestrator.events import BUS, OrchestratorEvent
from app.orchestrator.registry import AgentRegistry, DEFAULT_REGISTRY
from app.orchestrator.types import Plan, PlanStep, TypedResult


def dispatch_plan(
    plan: Plan,
    *,
    context: AgentContext,
    run_id: str,
    timeout_seconds: float,
    retries: int,
    is_cancelled: Callable[[], bool],
    registry: AgentRegistry | None = None,
    emit: Callable[[OrchestratorEvent], None] | None = None,
) -> dict[str, TypedResult]:
    book = registry or DEFAULT_REGISTRY
    publish = emit or BUS.emit
    results: dict[str, TypedResult] = {}
    remaining = {step.id: step for step in plan.steps}

    while remaining:
        if is_cancelled():
            for step in remaining.values():
                step.status = "skipped"
                results[step.id] = _skipped(step, "Run cancelled.")
                _emit_failed_or_skip(publish, run_id, step, skipped=True)
            break
        ready = [
            step
            for step in remaining.values()
            if all(dep in results for dep in step.depends_on)
        ]
        if not ready:
            for step in remaining.values():
                step.status = "skipped"
                results[step.id] = _skipped(step, "Blocked on an unfinished dependency.")
                _emit_failed_or_skip(publish, run_id, step, skipped=True)
            break

        failed_deps = []
        runnable: list[PlanStep] = []
        for step in ready:
            dep_results = [results[dep] for dep in step.depends_on]
            if any(item.status in {"failed", "skipped"} for item in dep_results):
                failed_deps.append(step)
            else:
                runnable.append(step)

        for step in failed_deps:
            step.status = "skipped"
            results[step.id] = _skipped(step, "Skipped because a dependency failed.")
            remaining.pop(step.id)
            _emit_failed_or_skip(publish, run_id, step, skipped=True)

        if not runnable:
            continue

        for step in runnable:
            step.status = "running"
            publish(
                OrchestratorEvent(
                    type="step_started",
                    run_id=run_id,
                    payload={"step_id": step.id, "agent": step.agent, "task": step.task},
                )
            )

        if len(runnable) == 1:
            step = runnable[0]
            results[step.id] = _run_one(
                step,
                context=context,
                run_id=run_id,
                timeout_seconds=timeout_seconds,
                retries=retries,
                registry=book,
                publish=publish,
                inputs={dep: results[dep] for dep in step.depends_on},
            )
            remaining.pop(step.id)
            continue

        with ThreadPoolExecutor(max_workers=len(runnable)) as pool:
            futures = {
                pool.submit(
                    _run_one_threaded,
                    step,
                    business_id=context.business_id,
                    user_id=context.user_id,
                    role=context.role,
                    parent_run_id=run_id,
                    timeout_seconds=timeout_seconds,
                    retries=retries,
                    registry=book,
                    inputs={dep: results[dep] for dep in step.depends_on},
                ): step
                for step in runnable
            }
            for future, step in futures.items():
                results[step.id] = future.result()
                remaining.pop(step.id)
                _publish_result(publish, run_id, step, results[step.id])

    return results


def _run_one_threaded(
    step: PlanStep,
    *,
    business_id: str,
    user_id: str,
    role: str,
    parent_run_id: str,
    timeout_seconds: float,
    retries: int,
    registry: AgentRegistry,
    inputs: dict[str, TypedResult],
) -> TypedResult:
    session = SessionLocal()
    try:
        context = AgentContext(
            session=session,
            business_id=business_id,
            user_id=user_id,
            role=role,
            run_id=parent_run_id,
        )
        result = _invoke_with_retry(
            step,
            context=context,
            timeout_seconds=timeout_seconds,
            retries=retries,
            registry=registry,
            inputs=inputs,
        )
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _run_one(
    step: PlanStep,
    *,
    context: AgentContext,
    run_id: str,
    timeout_seconds: float,
    retries: int,
    registry: AgentRegistry,
    publish: Callable[[OrchestratorEvent], None],
    inputs: dict[str, TypedResult],
) -> TypedResult:
    result = _invoke_with_retry(
        step,
        context=context,
        timeout_seconds=timeout_seconds,
        retries=retries,
        registry=registry,
        inputs=inputs,
    )
    _publish_result(publish, run_id, step, result)
    return result


def _invoke_with_retry(
    step: PlanStep,
    *,
    context: AgentContext,
    timeout_seconds: float,
    retries: int,
    registry: AgentRegistry,
    inputs: dict[str, TypedResult],
) -> TypedResult:
    attempts = max(retries, 0) + 1
    last_error = "Step failed."
    params = dict(step.params)
    params["_step_id"] = step.id
    for _attempt in range(attempts):
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    _call_agent,
                    registry,
                    step,
                    params,
                    inputs,
                    context,
                )
                result = future.result(timeout=timeout_seconds)
            result.step_id = step.id
            step.status = "completed" if result.status != "failed" else "failed"
            return result
        except FuturesTimeout:
            last_error = f"Step {step.id} timed out after {timeout_seconds}s."
        except Exception as exc:
            last_error = str(exc)
    step.status = "failed"
    step.error = last_error
    return TypedResult(
        step_id=step.id,
        agent=step.agent,
        task=step.task,
        status="failed",
        card_type="text",
        message=last_error,
    )


def _call_agent(
    registry: AgentRegistry,
    step: PlanStep,
    params: dict[str, Any],
    inputs: dict[str, TypedResult],
    context: AgentContext,
) -> TypedResult:
    return registry.run_task(
        agent=step.agent,
        task=step.task,
        params=params,
        inputs=inputs,
        context=context,
        step_id=step.id,
    )


def _skipped(step: PlanStep, message: str) -> TypedResult:
    return TypedResult(
        step_id=step.id,
        agent=step.agent,
        task=step.task,
        status="skipped",
        card_type="text",
        message=message,
    )


def _publish_result(
    publish: Callable[[OrchestratorEvent], None],
    run_id: str,
    step: PlanStep,
    result: TypedResult,
) -> None:
    if result.status == "failed":
        publish(
            OrchestratorEvent(
                type="step_failed",
                run_id=run_id,
                payload={"step_id": step.id, "agent": step.agent, "task": step.task, "error": result.message},
            )
        )
        return
    publish(
        OrchestratorEvent(
            type="step_done",
            run_id=run_id,
            payload={
                "step_id": step.id,
                "agent": step.agent,
                "task": step.task,
                "status": result.status,
                "result_type": result.card_type,
            },
        )
    )


def _emit_failed_or_skip(
    publish: Callable[[OrchestratorEvent], None],
    run_id: str,
    step: PlanStep,
    *,
    skipped: bool,
) -> None:
    publish(
        OrchestratorEvent(
            type="step_failed" if not skipped else "step_done",
            run_id=run_id,
            payload={
                "step_id": step.id,
                "agent": step.agent,
                "task": step.task,
                "status": "skipped" if skipped else "failed",
                "error": step.error,
            },
        )
    )
