from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.context import AgentContext
from app.agents.exception_monitor import ExceptionMonitorAgent
from app.agents.runs import finish_agent_run, start_agent_run
from app.llm.prompts.registry import get_prompt
from app.models import AutonomyRules, Business, User
from app.models.types import utcnow
from app.services.settings import get_autonomy_rules, mark_exception_scan_run


def run_exception_scans(
    session: Session,
    *,
    business_id: str | None = None,
    actor_user_id: str | None = None,
    force: bool = False,
    respect_hour: bool = False,
) -> dict[str, object]:
    now = utcnow()
    today = now.date()
    hour = now.hour
    targets = _scan_targets(session, business_id=business_id)
    ran: list[dict[str, object]] = []
    skipped = 0
    for rules, owner in targets:
        if owner is None:
            skipped += 1
            continue
        if not force and not rules.exception_scan_enabled:
            skipped += 1
            continue
        if respect_hour and not force and rules.exception_scan_hour_utc != hour:
            skipped += 1
            continue
        if not force and rules.exception_scan_last_run_on == today:
            skipped += 1
            continue
        actor = actor_user_id or owner.id
        result = _run_one(
            session,
            business_id=rules.business_id,
            actor_user_id=actor,
            role=owner.role or "owner",
        )
        mark_exception_scan_run(session, business_id=rules.business_id, ran_on=today)
        ran.append(result)
    session.flush()
    return {
        "ran": len(ran),
        "skipped": skipped,
        "businesses": ran,
        "ran_on": today,
    }


def _run_one(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    role: str,
) -> dict[str, object]:
    prompt = get_prompt("exception_rank")
    run = start_agent_run(
        session,
        business_id=business_id,
        agent_name="exception_monitor",
        actor_user_id=actor_user_id,
        prompt_name=prompt.name,
        prompt_version=prompt.version,
    )
    context = AgentContext(
        session=session,
        business_id=business_id,
        user_id=actor_user_id,
        role=role,
        run_id=run.id,
    )
    agent = ExceptionMonitorAgent()
    agent.attach(context)
    try:
        typed = agent.typed_result("scan", {}, step_id="scan")
        finish_agent_run(session, run=run, status="completed")
    except Exception as exc:
        finish_agent_run(session, run=run, status="failed", error_message=str(exc))
        raise
    items = typed.data.get("items") if isinstance(typed.data, dict) else []
    count = len(items) if isinstance(items, list) else 0
    return {
        "business_id": business_id,
        "run_id": run.id,
        "findings": count,
        "status": typed.status,
    }


def _scan_targets(
    session: Session,
    *,
    business_id: str | None,
) -> list[tuple[AutonomyRules, User | None]]:
    if business_id:
        ids = [business_id]
    else:
        ids = [row.id for row in session.scalars(select(Business)).all()]
    owners = {
        user.business_id: user
        for user in session.scalars(
            select(User).where(User.role == "owner", User.is_active.is_(True))
        ).all()
        if user.business_id
    }
    targets: list[tuple[AutonomyRules, User | None]] = []
    for bid in ids:
        get_autonomy_rules(session, business_id=bid)
        rules = session.scalar(select(AutonomyRules).where(AutonomyRules.business_id == bid))
        if rules is None:
            continue
        targets.append((rules, owners.get(bid)))
    return targets
