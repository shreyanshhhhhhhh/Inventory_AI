"""Pure-code purchase-proposal checks. No language model.

Every agent draft purchase suggestion must pass `validate_po_proposal` before a
row is inserted. Approving that suggestion is the only agent path that creates
a purchase order, and it runs this check again.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Business, PurchaseOrder, PurchaseOrderItem
from app.repositories import catalog as catalog_repo
from app.services.settings import get_autonomy_rules

_OPEN_PO_STATUSES = ("draft", "approved", "sent")
_po_gate: ContextVar[bool] = ContextVar("po_guardrail_gate", default=False)


@dataclass(frozen=True)
class PoLineProposal:
    product_id: str
    quantity: Decimal
    unit_cost: Decimal | None


@dataclass(frozen=True)
class PoProposal:
    supplier_id: str
    lines: tuple[PoLineProposal, ...]
    location_id: str | None = None


@dataclass(frozen=True)
class GuardrailResult:
    passed: bool
    reasons: tuple[str, ...]
    required_approval: str
    total: Decimal

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "reasons": list(self.reasons),
            "required_approval": self.required_approval,
            "total": str(self.total),
        }


def guardrail_gate_open() -> bool:
    return _po_gate.get()


@contextmanager
def po_write_gate():
    """Opened only after `validate_po_proposal` has passed."""
    token = _po_gate.set(True)
    try:
        yield
    finally:
        _po_gate.reset(token)


def proposal_from_mapping(payload: object) -> PoProposal | None:
    if not isinstance(payload, dict):
        return None
    supplier_id = payload.get("supplier_id")
    raw_lines = payload.get("lines")
    if not isinstance(supplier_id, str) or not supplier_id.strip():
        return None
    if not isinstance(raw_lines, list):
        return None
    lines: list[PoLineProposal] = []
    for raw in raw_lines:
        if not isinstance(raw, dict):
            return None
        product_id = raw.get("product_id")
        if not isinstance(product_id, str) or not product_id.strip():
            return None
        try:
            quantity = Decimal(str(raw.get("quantity")))
        except Exception:
            return None
        cost_raw = raw.get("unit_cost")
        if cost_raw is None:
            unit_cost = None
        else:
            try:
                unit_cost = Decimal(str(cost_raw))
            except Exception:
                return None
        lines.append(
            PoLineProposal(product_id=product_id, quantity=quantity, unit_cost=unit_cost)
        )
    location = payload.get("location_id")
    location_id = location if isinstance(location, str) and location.strip() else None
    return PoProposal(supplier_id=supplier_id.strip(), lines=tuple(lines), location_id=location_id)


def validate_po_proposal(
    proposal: PoProposal,
    business: Business,
    *,
    session: Session,
) -> GuardrailResult:
    reasons: list[str] = []

    def add(code: str) -> None:
        if code not in reasons:
            reasons.append(code)

    supplier = catalog_repo.get_supplier(session, business.id, proposal.supplier_id)
    if supplier is None:
        add("unknown_supplier")
    elif supplier.archived_at is not None:
        add("inactive_supplier")

    if not proposal.lines:
        add("empty_proposal")
    if len(proposal.lines) > settings.po_max_lines:
        add("too_many_lines")

    seen_products: set[str] = set()
    total = Decimal("0")
    line_limit = Decimal(settings.po_max_line_quantity)
    tolerance = Decimal(str(settings.po_cost_tolerance_ratio))
    for line in proposal.lines:
        if line.product_id in seen_products:
            add("duplicate_sku")
        seen_products.add(line.product_id)

        product = catalog_repo.get_product(session, business.id, line.product_id)
        if product is None or product.archived_at is not None:
            add("unknown_sku")

        quantity = line.quantity
        if not isinstance(quantity, Decimal) or not quantity.is_finite() or quantity <= 0:
            add("quantity_not_positive")
        elif quantity != quantity.to_integral_value():
            add("quantity_not_integer")
        elif quantity > line_limit:
            add("quantity_exceeds_line_limit")

        if line.unit_cost is None:
            add("missing_unit_cost")
            continue
        if not line.unit_cost.is_finite() or line.unit_cost < 0:
            add("cost_mismatch")
            continue

        link = catalog_repo.get_product_supplier_link(
            session,
            business.id,
            line.product_id,
            proposal.supplier_id,
        )
        if link is None:
            add("missing_supplier_cost")
        elif not _cost_matches(line.unit_cost, link.unit_cost, tolerance):
            add("cost_mismatch")

        if quantity.is_finite() and quantity > 0 and line.unit_cost.is_finite():
            total += quantity * line.unit_cost

    if total > Decimal(str(settings.po_max_total)):
        add("total_exceeds_limit")

    if _open_po_covers(session, business.id, proposal):
        add("duplicate_open_po")

    passed = not reasons
    return GuardrailResult(
        passed=passed,
        reasons=tuple(reasons),
        required_approval=_approval_level(session, business.id, total) if passed else "human",
        total=total,
    )


def _cost_matches(proposed: Decimal, expected: Decimal, tolerance: Decimal) -> bool:
    if expected == 0:
        return proposed == 0
    return abs(proposed - expected) / abs(expected) <= tolerance


def _approval_level(session: Session, business_id: str, total: Decimal) -> str:
    rules = get_autonomy_rules(session, business_id=business_id)
    amount = rules.get("auto_approve_below_amount")
    if amount is None:
        return "human"
    threshold = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    if total < threshold:
        return "auto"
    return "human"


def _open_po_covers(session: Session, business_id: str, proposal: PoProposal) -> bool:
    if not proposal.lines:
        return False
    product_ids = [line.product_id for line in proposal.lines]
    rows = session.execute(
        select(
            PurchaseOrderItem.product_id,
            func.coalesce(func.sum(PurchaseOrderItem.quantity_ordered), 0),
        )
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id)
        .where(
            PurchaseOrder.business_id == business_id,
            PurchaseOrderItem.business_id == business_id,
            PurchaseOrder.status.in_(_OPEN_PO_STATUSES),
            PurchaseOrderItem.product_id.in_(product_ids),
        )
        .group_by(PurchaseOrderItem.product_id)
    ).all()
    covered = {row[0]: Decimal(row[1]) for row in rows}
    for line in proposal.lines:
        if not line.quantity.is_finite() or line.quantity <= 0:
            continue
        if covered.get(line.product_id, Decimal("0")) >= line.quantity:
            return True
    return False
