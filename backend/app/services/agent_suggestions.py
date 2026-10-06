from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.jsonutil import jsonable
from app.models import AgentSuggestion
from app.models.types import new_id, utcnow
from app.repositories.businesses import get_business
from app.services.audit import log_action
from app.services.guardrail import (
    guardrail_gate_open,
    po_write_gate,
    proposal_from_mapping,
    validate_po_proposal,
)
from app.services.purchase_orders import PurchaseOrderError, create_po

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
    if suggestion_type == "draft_po" and not guardrail_gate_open():
        raise AgentSuggestionError(
            "Purchase suggestions must pass the guardrail.",
            code="guardrail_required",
        )
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


def create_guarded_po_suggestion(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    actor_role: str,
    run_id: str,
    payload: dict[str, object],
) -> dict[str, object]:
    """Validate a purchase proposal, then insert one `draft_po` suggestion.

    Auto-approve runs only when the owner has set `auto_approve_below_amount`
    and the proposal total is below that amount. The purchase order stays draft.
    """
    business = get_business(session, business_id)
    if business is None:
        raise AgentSuggestionError("Business not found.", status_code=404, code="not_found")
    proposal = proposal_from_mapping(payload)
    if proposal is None:
        raise AgentSuggestionError(
            "Purchase proposal is malformed.",
            code="guardrail_rejected",
        )
    result = validate_po_proposal(proposal, business, session=session)
    if not result.passed:
        raise AgentSuggestionError(
            "Purchase proposal failed the guardrail: " + ", ".join(result.reasons),
            code="guardrail_rejected",
        )
    stored = {
        **payload,
        "supplier_id": proposal.supplier_id,
        "location_id": proposal.location_id,
        "lines": [
            {
                "product_id": line.product_id,
                "quantity": line.quantity,
                "unit_cost": line.unit_cost,
            }
            for line in proposal.lines
        ],
        "guardrail": result.to_dict(),
        "decisions": [],
        "total": result.total,
    }
    with po_write_gate():
        created = create_suggestion(
            session,
            business_id=business_id,
            actor_user_id=actor_user_id,
            run_id=run_id,
            suggestion_type="draft_po",
            payload=stored,
        )
    if result.required_approval == "auto" and actor_role == "owner":
        return approve_suggestion(
            session,
            business_id=business_id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            suggestion_id=str(created["id"]),
            auto=True,
        )
    return created


def approve_suggestion(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    actor_role: str,
    suggestion_id: str,
    auto: bool = False,
) -> dict[str, object]:
    if actor_role != "owner":
        raise AgentSuggestionError(
            "Only the owner can approve a purchase suggestion.",
            status_code=403,
            code="forbidden",
        )
    suggestion = _get_or_error(session, business_id=business_id, suggestion_id=suggestion_id)
    extra = suggestion.payload.get("extra") if isinstance(suggestion.payload, dict) else None
    extra_action = extra.get("action") if isinstance(extra, dict) else None
    if suggestion.suggestion_type == "generic" and extra_action == "update_po_expected_date":
        return _approve_expected_date(
            session,
            suggestion=suggestion,
            business_id=business_id,
            actor_user_id=actor_user_id,
        )
    if suggestion.suggestion_type != "draft_po":
        raise AgentSuggestionError("Only purchase suggestions can be approved.")
    if suggestion.status != "pending":
        raise AgentSuggestionError("This suggestion is no longer pending.", code="conflict", status_code=409)
    business = get_business(session, business_id)
    if business is None:
        raise AgentSuggestionError("Business not found.", status_code=404, code="not_found")
    proposal = proposal_from_mapping(suggestion.payload)
    if proposal is None:
        raise AgentSuggestionError("Purchase proposal is malformed.", code="guardrail_rejected")
    result = validate_po_proposal(proposal, business, session=session)
    if not result.passed:
        raise AgentSuggestionError(
            "Purchase proposal failed the guardrail: " + ", ".join(result.reasons),
            code="guardrail_rejected",
        )
    action = "auto_approved" if auto else "approved"
    _append_decision(
        suggestion,
        {
            "action": action,
            "reason": None,
            "actor_user_id": actor_user_id,
            "at": utcnow().isoformat(),
        },
    )
    suggestion.status = "approved"
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="agent.suggestion.approve",
        entity_type="agent_suggestion",
        entity_id=suggestion.id,
        before_data={"status": "pending"},
        after_data={"status": "approved", "action": action, "guardrail": result.to_dict()},
    )
    session.flush()
    notes = suggestion.payload.get("notes") if isinstance(suggestion.payload, dict) else None
    try:
        po = create_po(
            session,
            business_id=business_id,
            actor_user_id=actor_user_id,
            supplier_id=proposal.supplier_id,
            expected_date=None,
            location_id=proposal.location_id,
            notes=notes if isinstance(notes, str) else None,
            line_items=[
                {
                    "product_id": line.product_id,
                    "quantity": line.quantity,
                    "unit_cost": line.unit_cost,
                }
                for line in proposal.lines
            ],
        )
    except PurchaseOrderError as exc:
        session.rollback()
        raise AgentSuggestionError(exc.message, status_code=exc.status_code, code=exc.code) from exc
    session.refresh(suggestion)
    body = dict(suggestion.payload or {})
    decisions = list(body.get("decisions") or [])
    if decisions and isinstance(decisions[-1], dict):
        last = dict(decisions[-1])
        last["purchase_order_id"] = str(po["id"])
        decisions[-1] = last
    body["decisions"] = decisions
    body["purchase_order_id"] = str(po["id"])
    body["guardrail"] = result.to_dict()
    suggestion.payload = jsonable(body)
    session.commit()
    session.refresh(suggestion)
    return _payload(suggestion)


def reject_suggestion(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    actor_role: str,
    suggestion_id: str,
    reason: str,
) -> dict[str, object]:
    if actor_role != "owner":
        raise AgentSuggestionError(
            "Only the owner can reject a purchase suggestion.",
            status_code=403,
            code="forbidden",
        )
    cleaned = reason.strip()
    if not cleaned:
        raise AgentSuggestionError("A rejection reason is required.")
    suggestion = _get_or_error(session, business_id=business_id, suggestion_id=suggestion_id)
    extra = suggestion.payload.get("extra") if isinstance(suggestion.payload, dict) else None
    extra_action = extra.get("action") if isinstance(extra, dict) else None
    if suggestion.suggestion_type not in {"draft_po"} and extra_action != "update_po_expected_date":
        raise AgentSuggestionError("Only purchase suggestions can be rejected.")
    if suggestion.status != "pending":
        raise AgentSuggestionError("This suggestion is no longer pending.", code="conflict", status_code=409)
    _append_decision(
        suggestion,
        {
            "action": "rejected",
            "reason": cleaned,
            "actor_user_id": actor_user_id,
            "at": utcnow().isoformat(),
        },
    )
    suggestion.status = "rejected"
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="agent.suggestion.reject",
        entity_type="agent_suggestion",
        entity_id=suggestion.id,
        before_data={"status": "pending"},
        after_data={"status": "rejected", "reason": cleaned},
    )
    session.commit()
    session.refresh(suggestion)
    return _payload(suggestion)


def list_suggestions(
    session: Session,
    *,
    business_id: str,
    run_id: str | None = None,
) -> list[dict[str, object]]:
    query = select(AgentSuggestion).where(AgentSuggestion.business_id == business_id)
    if run_id is not None:
        query = query.where(AgentSuggestion.run_id == run_id)
    rows = session.scalars(query.order_by(AgentSuggestion.created_at.asc())).all()
    return [_payload(row) for row in rows]


def _approve_expected_date(
    session: Session,
    *,
    suggestion: AgentSuggestion,
    business_id: str,
    actor_user_id: str,
) -> dict[str, object]:
    from datetime import date as date_type

    from app.services.supplier_messages import SupplierMessageError, apply_expected_date_suggestion

    if suggestion.status != "pending":
        raise AgentSuggestionError("This suggestion is no longer pending.", code="conflict", status_code=409)
    extra = suggestion.payload.get("extra") if isinstance(suggestion.payload, dict) else {}
    if not isinstance(extra, dict):
        extra = {}
    purchase_order_id = str(extra.get("purchase_order_id") or "")
    raw_date = str(extra.get("expected_date") or "")
    try:
        expected_date = date_type.fromisoformat(raw_date[:10])
    except ValueError as exc:
        raise AgentSuggestionError("The suggested date is invalid.") from exc
    try:
        apply_expected_date_suggestion(
            session,
            business_id=business_id,
            actor_user_id=actor_user_id,
            purchase_order_id=purchase_order_id,
            expected_date=expected_date,
        )
    except SupplierMessageError as exc:
        raise AgentSuggestionError(exc.message, status_code=exc.status_code, code=exc.code) from exc
    suggestion.status = "approved"
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="agent.suggestion.approve",
        entity_type="agent_suggestion",
        entity_id=suggestion.id,
        before_data={"status": "pending"},
        after_data={"status": "approved", "action": "update_po_expected_date"},
    )
    session.commit()
    session.refresh(suggestion)
    return _payload(suggestion)


def _get_or_error(
    session: Session,
    *,
    business_id: str,
    suggestion_id: str,
) -> AgentSuggestion:
    suggestion = session.scalar(
        select(AgentSuggestion).where(
            AgentSuggestion.business_id == business_id,
            AgentSuggestion.id == suggestion_id,
        )
    )
    if suggestion is None:
        raise AgentSuggestionError(
            "Suggestion not found.",
            status_code=404,
            code="not_found",
        )
    return suggestion


def _append_decision(suggestion: AgentSuggestion, decision: dict[str, object]) -> None:
    payload = dict(suggestion.payload or {})
    decisions = [item for item in list(payload.get("decisions") or []) if isinstance(item, dict)]
    decisions.append(decision)
    payload["decisions"] = decisions
    suggestion.payload = payload


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
