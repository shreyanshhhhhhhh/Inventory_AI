"""Ordered playbook actions per exception type. Preconditions are checked in code."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from app.services.detectors import DetectorFinding

PLAYBOOK_ACTIONS = frozenset(
    {
        "alternate_supplier",
        "expedite",
        "reorder_now",
        "transfer_stock",
        "count_stock",
        "ignore",
    }
)

APPROVAL_ACTIONS = frozenset(PLAYBOOK_ACTIONS - {"ignore"})


@dataclass(frozen=True)
class PlaybookContext:
    supplier_count: int
    has_open_po: bool
    other_location_has_stock: bool
    other_location_is_low: bool


Precondition = Callable[[PlaybookContext], bool]


def _always(_ctx: PlaybookContext) -> bool:
    return True


def _has_supplier(ctx: PlaybookContext) -> bool:
    return ctx.supplier_count >= 1


def _has_alternate(ctx: PlaybookContext) -> bool:
    return ctx.supplier_count >= 2


def _has_open_po(ctx: PlaybookContext) -> bool:
    return ctx.has_open_po


def _can_transfer(ctx: PlaybookContext) -> bool:
    return ctx.other_location_has_stock


def _overstock_transfer(ctx: PlaybookContext) -> bool:
    return ctx.other_location_is_low


PLAYBOOKS: dict[str, list[tuple[str, Precondition]]] = {
    "stockout_risk": [
        ("reorder_now", _has_supplier),
        ("expedite", _has_open_po),
        ("alternate_supplier", _has_alternate),
        ("transfer_stock", _can_transfer),
        ("ignore", _always),
    ],
    "overstock": [
        ("transfer_stock", _overstock_transfer),
        ("count_stock", _always),
        ("ignore", _always),
    ],
    "demand_spike": [
        ("reorder_now", _has_supplier),
        ("expedite", _has_open_po),
        ("ignore", _always),
    ],
    "demand_drop": [
        ("count_stock", _always),
        ("ignore", _always),
    ],
    "supplier_delay": [
        ("expedite", _always),
        ("alternate_supplier", _has_alternate),
        ("ignore", _always),
    ],
    "data_anomaly": [
        ("count_stock", _always),
        ("ignore", _always),
    ],
}


def candidate_actions(finding: DetectorFinding, ctx: PlaybookContext) -> list[str]:
    steps = PLAYBOOKS.get(finding.exception_type, [("ignore", _always)])
    return [action for action, allowed in steps if allowed(ctx)]


def clip_action(chosen: str | None, allowed: list[str]) -> str:
    if allowed and chosen in allowed:
        return chosen
    if allowed:
        return allowed[0]
    return "ignore"


def needs_approval(action: str) -> bool:
    return action in APPROVAL_ACTIONS
