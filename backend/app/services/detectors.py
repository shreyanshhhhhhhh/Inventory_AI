"""Deterministic exception detectors. Pure functions: numbers and dates from snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from statistics import median

DEFAULT_LEAD_TIME_DAYS = 7
OVERSTOCK_DAYS = 90
OVERSTOCK_HIGH_DAYS = 180
SPIKE_RATIO = Decimal("1.5")
DROP_RATIO = Decimal("0.5")
ROBUST_Z = Decimal("2.5")
MAD_SCALE = Decimal("1.4826")
RELIABILITY_SCORE_MAX = 0.7
RELIABILITY_OVERDUE_MIN = 2
UNRECONCILED_MULT = Decimal("3")
UNRECONCILED_ABS_FLOOR = Decimal("100")
_QUANTUM = Decimal("0.0001")
_ZERO = Decimal("0")

EXCEPTION_TYPES = (
    "stockout_risk",
    "overstock",
    "demand_spike",
    "demand_drop",
    "supplier_delay",
    "data_anomaly",
)
SEVERITIES = ("low", "medium", "high", "critical")


@dataclass(frozen=True)
class DetectorFinding:
    exception_type: str
    severity: str
    title: str
    entity_type: str
    entity_id: str
    dedupe_key: str
    evidence: dict[str, object]


@dataclass(frozen=True)
class ProductCoverSnapshot:
    product_id: str
    sku: str
    product_name: str
    on_hand: Decimal
    daily_demand: Decimal
    lead_time_days: int
    location_on_hand: dict[str, Decimal]


@dataclass(frozen=True)
class DemandSnapshot:
    product_id: str
    sku: str
    product_name: str
    last_7_units: Decimal
    forecast_7_units: Decimal
    prior_week_totals: tuple[Decimal, ...]


@dataclass(frozen=True)
class PurchaseOrderSnapshot:
    po_id: str
    po_number: str
    supplier_id: str
    supplier_name: str
    status: str
    expected_on: date | None
    product_ids: tuple[str, ...]


@dataclass(frozen=True)
class SupplierReliabilitySnapshot:
    supplier_id: str
    supplier_name: str
    reliability_score: float
    overdue_count: int


@dataclass(frozen=True)
class MovementSnapshot:
    movement_id: str
    product_id: str
    sku: str
    product_name: str
    location_id: str
    movement_type: str
    quantity: Decimal
    occurred_at: datetime
    reason: str | None
    note: str | None


def detect_stockout_risk(rows: list[ProductCoverSnapshot]) -> list[DetectorFinding]:
    findings: list[DetectorFinding] = []
    for row in rows:
        lead = row.lead_time_days if row.lead_time_days > 0 else DEFAULT_LEAD_TIME_DAYS
        if row.daily_demand <= 0:
            continue
        days_of_cover = _q(row.on_hand / row.daily_demand)
        if row.on_hand <= 0:
            findings.append(
                _finding(
                    exception_type="stockout_risk",
                    severity="critical",
                    title=f"{row.sku} is out of stock with ongoing demand",
                    entity_type="product",
                    entity_id=row.product_id,
                    evidence={
                        "sku": row.sku,
                        "product_name": row.product_name,
                        "on_hand": row.on_hand,
                        "daily_demand": row.daily_demand,
                        "lead_time_days": lead,
                        "days_of_cover": days_of_cover,
                    },
                )
            )
            continue
        if days_of_cover < Decimal(lead):
            severity = "high" if days_of_cover < (Decimal(lead) / Decimal(2)) else "medium"
            findings.append(
                _finding(
                    exception_type="stockout_risk",
                    severity=severity,
                    title=f"{row.sku} is projected to stock out before lead time",
                    entity_type="product",
                    entity_id=row.product_id,
                    evidence={
                        "sku": row.sku,
                        "product_name": row.product_name,
                        "on_hand": row.on_hand,
                        "daily_demand": row.daily_demand,
                        "lead_time_days": lead,
                        "days_of_cover": days_of_cover,
                    },
                )
            )
    return findings


def detect_overstock(rows: list[ProductCoverSnapshot]) -> list[DetectorFinding]:
    findings: list[DetectorFinding] = []
    for row in rows:
        if row.daily_demand <= 0 or row.on_hand <= 0:
            continue
        days_of_cover = _q(row.on_hand / row.daily_demand)
        if days_of_cover <= Decimal(OVERSTOCK_DAYS):
            continue
        severity = "high" if days_of_cover > Decimal(OVERSTOCK_HIGH_DAYS) else "medium"
        findings.append(
            _finding(
                exception_type="overstock",
                severity=severity,
                title=f"{row.sku} has more than {OVERSTOCK_DAYS} days of cover",
                entity_type="product",
                entity_id=row.product_id,
                evidence={
                    "sku": row.sku,
                    "product_name": row.product_name,
                    "on_hand": row.on_hand,
                    "daily_demand": row.daily_demand,
                    "days_of_cover": days_of_cover,
                    "overstock_days": OVERSTOCK_DAYS,
                },
            )
        )
    return findings


def detect_demand_shift(rows: list[DemandSnapshot]) -> list[DetectorFinding]:
    findings: list[DetectorFinding] = []
    for row in rows:
        ratio = _demand_ratio(row.last_7_units, row.forecast_7_units)
        z_score = _robust_z(row.last_7_units, row.prior_week_totals)
        spike = (ratio is not None and ratio > SPIKE_RATIO) or (
            z_score is not None and z_score > ROBUST_Z
        )
        drop = (ratio is not None and ratio < DROP_RATIO) or (
            z_score is not None and z_score < -ROBUST_Z
        )
        if row.last_7_units == 0 and row.forecast_7_units == 0:
            continue
        if spike and not drop:
            findings.append(
                _finding(
                    exception_type="demand_spike",
                    severity="high" if ratio is not None and ratio >= Decimal("2") else "medium",
                    title=f"{row.sku} demand spiked versus the forecast",
                    entity_type="product",
                    entity_id=row.product_id,
                    evidence={
                        "sku": row.sku,
                        "product_name": row.product_name,
                        "last_7_units": row.last_7_units,
                        "forecast_7_units": row.forecast_7_units,
                        "ratio": ratio,
                        "robust_z": z_score,
                    },
                )
            )
        elif drop and not spike:
            findings.append(
                _finding(
                    exception_type="demand_drop",
                    severity="medium",
                    title=f"{row.sku} demand dropped versus the forecast",
                    entity_type="product",
                    entity_id=row.product_id,
                    evidence={
                        "sku": row.sku,
                        "product_name": row.product_name,
                        "last_7_units": row.last_7_units,
                        "forecast_7_units": row.forecast_7_units,
                        "ratio": ratio,
                        "robust_z": z_score,
                    },
                )
            )
    return findings


def detect_supplier_delay(
    orders: list[PurchaseOrderSnapshot],
    suppliers: list[SupplierReliabilitySnapshot],
    *,
    today: date,
) -> list[DetectorFinding]:
    findings: list[DetectorFinding] = []
    open_statuses = {"approved", "sent"}
    for order in orders:
        if order.status not in open_statuses:
            continue
        if order.expected_on is None or order.expected_on >= today:
            continue
        days_overdue = (today - order.expected_on).days
        findings.append(
            _finding(
                exception_type="supplier_delay",
                severity="high" if days_overdue >= 7 else "medium",
                title=f"PO {order.po_number} is overdue from {order.supplier_name}",
                entity_type="purchase_order",
                entity_id=order.po_id,
                evidence={
                    "po_number": order.po_number,
                    "supplier_id": order.supplier_id,
                    "supplier_name": order.supplier_name,
                    "status": order.status,
                    "expected_on": order.expected_on.isoformat(),
                    "days_overdue": days_overdue,
                    "product_ids": list(order.product_ids),
                },
            )
        )
    for supplier in suppliers:
        if supplier.reliability_score >= RELIABILITY_SCORE_MAX:
            continue
        if supplier.overdue_count < RELIABILITY_OVERDUE_MIN:
            continue
        findings.append(
            DetectorFinding(
                exception_type="supplier_delay",
                severity="high",
                title=f"{supplier.supplier_name} reliability is degrading",
                entity_type="supplier",
                entity_id=supplier.supplier_id,
                dedupe_key=f"supplier_delay:reliability:{supplier.supplier_id}",
                evidence={
                    "supplier_id": supplier.supplier_id,
                    "supplier_name": supplier.supplier_name,
                    "reliability_score": supplier.reliability_score,
                    "overdue_count": supplier.overdue_count,
                },
            )
        )
    return findings


def detect_data_anomaly(
    stock_rows: list[ProductCoverSnapshot],
    movements: list[MovementSnapshot],
    forecast_units_by_product: dict[str, Decimal],
) -> list[DetectorFinding]:
    findings: list[DetectorFinding] = []
    for row in stock_rows:
        for location_id, on_hand in row.location_on_hand.items():
            if on_hand >= 0:
                continue
            findings.append(
                DetectorFinding(
                    exception_type="data_anomaly",
                    severity="high",
                    title=f"{row.sku} has negative on-hand at a location",
                    entity_type="product",
                    entity_id=row.product_id,
                    dedupe_key=f"data_anomaly:negative_stock:{row.product_id}:{location_id}",
                    evidence={
                        "sku": row.sku,
                        "product_name": row.product_name,
                        "location_id": location_id,
                        "on_hand": on_hand,
                    },
                )
            )
    findings.extend(_duplicate_sales(movements))
    findings.extend(_unreconciled_adjustments(movements, forecast_units_by_product))
    return findings


def _duplicate_sales(movements: list[MovementSnapshot]) -> list[DetectorFinding]:
    buckets: dict[tuple[str, str, str, str], list[MovementSnapshot]] = {}
    for row in movements:
        if row.movement_type != "sale":
            continue
        minute = row.occurred_at.replace(second=0, microsecond=0).isoformat()
        key = (row.product_id, row.location_id, minute, str(_q(abs(row.quantity))))
        buckets.setdefault(key, []).append(row)
    findings: list[DetectorFinding] = []
    for (product_id, location_id, minute, qty), group in buckets.items():
        if len(group) < 2:
            continue
        sample = group[0]
        findings.append(
            DetectorFinding(
                exception_type="data_anomaly",
                severity="medium",
                title=f"{sample.sku} has duplicate sales in the same minute",
                entity_type="product",
                entity_id=product_id,
                dedupe_key=f"data_anomaly:duplicate_sales:{product_id}:{location_id}:{minute}:{qty}",
                evidence={
                    "sku": sample.sku,
                    "product_name": sample.product_name,
                    "location_id": location_id,
                    "occurred_at": minute,
                    "quantity": Decimal(qty),
                    "duplicate_count": len(group),
                    "movement_ids": [item.movement_id for item in group],
                },
            )
        )
    return findings


def _unreconciled_adjustments(
    movements: list[MovementSnapshot],
    forecast_units_by_product: dict[str, Decimal],
) -> list[DetectorFinding]:
    findings: list[DetectorFinding] = []
    for row in movements:
        if row.movement_type != "adjustment":
            continue
        forecast = forecast_units_by_product.get(row.product_id, _ZERO)
        threshold = max(UNRECONCILED_ABS_FLOOR, _q(UNRECONCILED_MULT * forecast))
        if abs(row.quantity) <= threshold:
            continue
        findings.append(
            DetectorFinding(
                exception_type="data_anomaly",
                severity="medium",
                title=f"{row.sku} has an adjustment that does not reconcile",
                entity_type="stock_movement",
                entity_id=row.movement_id,
                dedupe_key=f"data_anomaly:unreconciled_adjustment:{row.movement_id}",
                evidence={
                    "sku": row.sku,
                    "product_name": row.product_name,
                    "quantity": row.quantity,
                    "occurred_at": row.occurred_at.isoformat(),
                    "forecast_units": forecast,
                    "threshold": threshold,
                    "reason": row.reason,
                    "note": row.note,
                },
            )
        )
    return findings


def _finding(
    *,
    exception_type: str,
    severity: str,
    title: str,
    entity_type: str,
    entity_id: str,
    evidence: dict[str, object],
) -> DetectorFinding:
    return DetectorFinding(
        exception_type=exception_type,
        severity=severity,
        title=title,
        entity_type=entity_type,
        entity_id=entity_id,
        dedupe_key=f"{exception_type}:{entity_id}",
        evidence=evidence,
    )


def _q(value: Decimal) -> Decimal:
    return value.quantize(_QUANTUM)


def _demand_ratio(last_7: Decimal, forecast_7: Decimal) -> Decimal | None:
    if forecast_7 > 0:
        return _q(last_7 / forecast_7)
    if last_7 > 0:
        return Decimal("999")
    return None


def _robust_z(value: Decimal, prior: tuple[Decimal, ...]) -> Decimal | None:
    if len(prior) < 3:
        return None
    samples = [float(item) for item in prior]
    mid = Decimal(str(median(samples)))
    deviations = [abs(float(item) - float(mid)) for item in prior]
    mad = Decimal(str(median(deviations)))
    if mad == 0:
        return None
    return _q((value - mid) / (MAD_SCALE * mad))


def lookback_start(today: date, *, days: int = 14) -> datetime:
    start = today - timedelta(days=days - 1)
    return datetime(start.year, start.month, start.day)
