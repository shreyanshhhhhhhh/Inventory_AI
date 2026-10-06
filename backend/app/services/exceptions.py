from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.jsonutil import jsonable
from app.models import InventoryException
from app.models.types import new_id
from app.services.audit import log_action


class ExceptionError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, code: str = "bad_request") -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


def get_exception(
    session: Session,
    *,
    business_id: str,
    exception_id: str,
) -> dict[str, object]:
    row = session.scalar(
        select(InventoryException).where(
            InventoryException.business_id == business_id,
            InventoryException.id == exception_id,
        )
    )
    if row is None:
        raise ExceptionError("Exception not found.", status_code=404, code="not_found")
    return _payload(row)


def get_open_by_dedupe(
    session: Session,
    *,
    business_id: str,
    dedupe_key: str,
) -> InventoryException | None:
    return session.scalar(
        select(InventoryException).where(
            InventoryException.business_id == business_id,
            InventoryException.dedupe_key == dedupe_key,
            InventoryException.status == "open",
        )
    )


def count_open(session: Session, *, business_id: str) -> int:
    from sqlalchemy import func

    total = session.scalar(
        select(func.count())
        .select_from(InventoryException)
        .where(
            InventoryException.business_id == business_id,
            InventoryException.status == "open",
        )
    )
    return int(total or 0)


def list_open(session: Session, *, business_id: str) -> list[dict[str, object]]:
    rows = session.scalars(
        select(InventoryException)
        .where(
            InventoryException.business_id == business_id,
            InventoryException.status == "open",
        )
        .order_by(InventoryException.created_at.asc())
    ).all()
    return [_payload(row) for row in rows]


def upsert_open(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    run_id: str | None,
    exception_type: str,
    severity: str,
    entity_type: str,
    entity_id: str,
    dedupe_key: str,
    title: str,
    evidence: dict[str, object],
    recommended_action: str | None,
    rationale: str | None,
    suggestion_id: str | None,
) -> tuple[dict[str, object], bool]:
    existing = get_open_by_dedupe(session, business_id=business_id, dedupe_key=dedupe_key)
    if existing is not None:
        before = _payload(existing)
        existing.severity = severity
        existing.title = title
        existing.evidence = jsonable(evidence)
        existing.recommended_action = recommended_action
        existing.rationale = rationale
        if run_id:
            existing.run_id = run_id
        session.flush()
        log_action(
            session,
            business_id=business_id,
            actor_user_id=actor_user_id,
            action="exception.update",
            entity_type="exception",
            entity_id=existing.id,
            before_data=jsonable(before),
            after_data=jsonable(_payload(existing)),
        )
        return _payload(existing), False

    row = InventoryException(
        id=new_id(),
        business_id=business_id,
        exception_type=exception_type,
        severity=severity,
        status="open",
        entity_type=entity_type,
        entity_id=entity_id,
        dedupe_key=dedupe_key,
        title=title,
        evidence=jsonable(evidence),
        recommended_action=recommended_action,
        rationale=rationale,
        suggestion_id=suggestion_id,
        run_id=run_id,
    )
    session.add(row)
    session.flush()
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="exception.create",
        entity_type="exception",
        entity_id=row.id,
        before_data=None,
        after_data=jsonable(_payload(row)),
    )
    return _payload(row), True


def attach_suggestion(
    session: Session,
    *,
    business_id: str,
    exception_id: str,
    suggestion_id: str,
) -> None:
    row = session.scalar(
        select(InventoryException).where(
            InventoryException.id == exception_id,
            InventoryException.business_id == business_id,
        )
    )
    if row is None:
        raise ExceptionError("Exception not found.", status_code=404, code="not_found")
    row.suggestion_id = suggestion_id
    session.flush()


def _payload(row: InventoryException) -> dict[str, object]:
    return {
        "id": row.id,
        "business_id": row.business_id,
        "exception_type": row.exception_type,
        "severity": row.severity,
        "status": row.status,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "dedupe_key": row.dedupe_key,
        "title": row.title,
        "evidence": row.evidence,
        "recommended_action": row.recommended_action,
        "rationale": row.rationale,
        "suggestion_id": row.suggestion_id,
        "run_id": row.run_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
