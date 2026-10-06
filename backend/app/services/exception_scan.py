"""Gather tenant snapshots and run detectors. Persistence is a separate step."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.playbooks import PlaybookContext, candidate_actions, clip_action, needs_approval
from app.core.jsonutil import jsonable
from app.models import Product, ProductSupplier, PurchaseOrderItem, StockMovement
from app.models.types import utcnow
from app.services import agent_suggestions as suggestion_service
from app.services import exceptions as exception_service
from app.services import supplier_reliability as reliability_service
from app.services.detectors import (
    DEFAULT_LEAD_TIME_DAYS,
    ChaseFollowupSnapshot,
    DemandSnapshot,
    DetectorFinding,
    MovementSnapshot,
    ProductCoverSnapshot,
    PurchaseOrderSnapshot,
    SupplierReliabilitySnapshot,
    detect_chase_no_reply,
    detect_data_anomaly,
    detect_demand_shift,
    detect_overstock,
    detect_stockout_risk,
    detect_supplier_delay,
)
from app.services.forecast import get_history, list_forecasts
from app.services.inventory import get_stock_levels
from app.services.purchase_orders import list_pos
from app.services.settings import get_autonomy_rules, mark_exception_scan_run
from app.services.supplier_messages import list_unanswered_chases

_ZERO = Decimal("0")


def detect_for_business(session: Session, *, business_id: str) -> list[dict[str, object]]:
    findings, contexts, forecast_meta = _run_detectors(session, business_id=business_id)
    items: list[dict[str, object]] = []
    for finding in findings:
        allowed = candidate_actions(finding, contexts.get(finding.dedupe_key, _empty_ctx()))
        items.append(
            {
                **_finding_dict(finding, forecast_meta),
                "candidate_actions": allowed,
            }
        )
    return items


def persist_ranked_findings(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    run_id: str,
    rankings: list[dict[str, Any]],
) -> list[dict[str, object]]:
    findings, contexts, forecast_meta = _run_detectors(session, business_id=business_id)
    rank_by_key = {str(item.get("dedupe_key")): item for item in rankings if item.get("dedupe_key")}
    stored: list[dict[str, object]] = []
    for finding in findings:
        allowed = candidate_actions(finding, contexts.get(finding.dedupe_key, _empty_ctx()))
        ranked = rank_by_key.get(finding.dedupe_key) or {}
        action = clip_action(ranked.get("action") if isinstance(ranked.get("action"), str) else None, allowed)
        rationale = str(ranked.get("rationale") or "Playbook default.").strip() or "Playbook default."
        existing = exception_service.get_open_by_dedupe(
            session,
            business_id=business_id,
            dedupe_key=finding.dedupe_key,
        )
        suggestion_id = existing.suggestion_id if existing is not None else None
        row, created = exception_service.upsert_open(
            session,
            business_id=business_id,
            actor_user_id=actor_user_id,
            run_id=run_id,
            exception_type=finding.exception_type,
            severity=finding.severity,
            entity_type=finding.entity_type,
            entity_id=finding.entity_id,
            dedupe_key=finding.dedupe_key,
            title=finding.title,
            evidence=_enrich_evidence(finding, forecast_meta),
            recommended_action=action,
            rationale=rationale,
            suggestion_id=suggestion_id,
        )
        if created and needs_approval(action):
            stored_evidence = _enrich_evidence(finding, forecast_meta)
            suggestion = suggestion_service.create_suggestion(
                session,
                business_id=business_id,
                actor_user_id=actor_user_id,
                run_id=run_id,
                suggestion_type="generic",
                payload={
                    "title": finding.title,
                    "summary": rationale,
                    "reason_codes": list(stored_evidence.get("reason_codes") or []),
                    "evidence": jsonable(stored_evidence),
                    "extra": {
                        "action": action,
                        "exception_id": row["id"],
                        "exception_type": finding.exception_type,
                        "dedupe_key": finding.dedupe_key,
                        "evidence": jsonable(stored_evidence),
                    },
                },
            )
            exception_service.attach_suggestion(
                session,
                business_id=business_id,
                exception_id=str(row["id"]),
                suggestion_id=str(suggestion["id"]),
            )
            row["suggestion_id"] = suggestion["id"]
        stored.append({**row, "candidate_actions": allowed, "created": created})
    session.flush()
    return stored


def run_nightly_scan(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    run_id: str,
    force: bool = False,
) -> dict[str, object] | None:
    rules = get_autonomy_rules(session, business_id=business_id)
    if not rules["exception_scan_enabled"] and not force:
        return None
    today = utcnow().date()
    last = rules.get("exception_scan_last_run_on")
    if last == today and not force:
        return {"skipped": True, "reason": "already_ran", "items": []}
    items = persist_ranked_findings(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        run_id=run_id,
        rankings=[],
    )
    mark_exception_scan_run(session, business_id=business_id, ran_on=today)
    return {"skipped": False, "items": items}


def _run_detectors(
    session: Session,
    *,
    business_id: str,
) -> tuple[list[DetectorFinding], dict[str, PlaybookContext], dict[str, object]]:
    today = utcnow().date()
    cover_rows, demand_rows, orders, suppliers, movements, forecast_map, chases, contexts, forecast_meta = _snapshots(
        session,
        business_id=business_id,
        today=today,
    )
    findings: list[DetectorFinding] = []
    findings.extend(detect_stockout_risk(cover_rows))
    findings.extend(detect_overstock(cover_rows))
    findings.extend(detect_demand_shift(demand_rows))
    findings.extend(detect_supplier_delay(orders, suppliers, today=today))
    findings.extend(detect_data_anomaly(cover_rows, movements, forecast_map))
    findings.extend(detect_chase_no_reply(chases))
    return findings, contexts, forecast_meta


def _snapshots(
    session: Session,
    *,
    business_id: str,
    today: date,
) -> tuple[
    list[ProductCoverSnapshot],
    list[DemandSnapshot],
    list[PurchaseOrderSnapshot],
    list[SupplierReliabilitySnapshot],
    list[MovementSnapshot],
    dict[str, Decimal],
    list[ChaseFollowupSnapshot],
    dict[str, PlaybookContext],
    dict[str, object],
]:
    products = list(
        session.scalars(
            select(Product).where(
                Product.business_id == business_id,
                Product.archived_at.is_(None),
            )
        ).all()
    )
    stock_items, _total = get_stock_levels(
        session,
        business_id=business_id,
        search=None,
        location_id=None,
        low_only=False,
        page=1,
        page_size=1000,
    )
    links = list(
        session.scalars(
            select(ProductSupplier).where(ProductSupplier.business_id == business_id)
        ).all()
    )
    links_by_product: dict[str, list[ProductSupplier]] = defaultdict(list)
    for link in links:
        links_by_product[link.product_id].append(link)

    listed = list_forecasts(session, business_id=business_id)
    forecast_by_id: dict[str, dict[str, object]] = {}
    raw_items = listed.get("items")
    if isinstance(raw_items, list):
        for item in raw_items:
            if isinstance(item, dict):
                forecast_by_id[str(item["product_id"])] = item

    loc_on_hand: dict[str, dict[str, Decimal]] = defaultdict(dict)
    product_on_hand: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    location_low: dict[str, bool] = defaultdict(bool)
    for item in stock_items:
        product_id = str(item["product_id"])
        location_id = str(item["location_id"])
        on_hand = Decimal(str(item["on_hand"]))
        loc_on_hand[product_id][location_id] = on_hand
        product_on_hand[product_id] += on_hand
        if str(item.get("status")) in {"low", "out"}:
            location_low[product_id] = True

    history = get_history(session, business_id=business_id)
    history_by_id: dict[str, list[Decimal]] = {}
    history_items = history.get("items")
    if isinstance(history_items, list):
        for item in history_items:
            if not isinstance(item, dict):
                continue
            series = item.get("history")
            values: list[Decimal] = []
            if isinstance(series, list):
                for point in series:
                    if isinstance(point, dict) and point.get("units") is not None:
                        values.append(Decimal(str(point["units"])))
            history_by_id[str(item["product_id"])] = values

    po_rows, _po_total = list_pos(session, business_id=business_id, page=1, page_size=500)
    po_ids = [str(row["id"]) for row in po_rows]
    line_rows = session.scalars(
        select(PurchaseOrderItem).where(
            PurchaseOrderItem.business_id == business_id,
            PurchaseOrderItem.purchase_order_id.in_(po_ids) if po_ids else PurchaseOrderItem.id.is_(None),
        )
    ).all()
    lines_by_po: dict[str, list[str]] = defaultdict(list)
    open_po_products: set[str] = set()
    for line in line_rows:
        lines_by_po[line.purchase_order_id].append(line.product_id)
        parent = next((row for row in po_rows if row["id"] == line.purchase_order_id), None)
        if parent and str(parent.get("status")) in {"approved", "sent", "draft"}:
            open_po_products.add(line.product_id)

    orders: list[PurchaseOrderSnapshot] = []
    for row in po_rows:
        expected = row.get("expected_date") or row.get("expected_on")
        expected_on = _as_date(expected)
        orders.append(
            PurchaseOrderSnapshot(
                po_id=str(row["id"]),
                po_number=str(row["po_number"]),
                supplier_id=str(row["supplier_id"]),
                supplier_name=str(row["supplier_name"]),
                status=str(row["status"]),
                expected_on=expected_on,
                product_ids=tuple(lines_by_po.get(str(row["id"]), [])),
            )
        )

    reliability = reliability_service.get_supplier_reliability(session, business_id=business_id)
    suppliers = [
        SupplierReliabilitySnapshot(
            supplier_id=str(item["supplier_id"]),
            supplier_name=str(item["supplier_name"]),
            reliability_score=float(item["reliability_score"]),
            overdue_count=int(item["overdue_count"]),
        )
        for item in reliability
    ]

    start = datetime.combine(today - timedelta(days=13), time.min, tzinfo=timezone.utc)
    end = datetime.combine(today, time.max, tzinfo=timezone.utc)
    movement_rows = session.scalars(
        select(StockMovement).where(
            StockMovement.business_id == business_id,
            StockMovement.occurred_at >= start,
            StockMovement.occurred_at <= end,
        )
    ).all()
    product_meta = {product.id: product for product in products}
    movements: list[MovementSnapshot] = []
    for row in movement_rows:
        product = product_meta.get(row.product_id)
        movements.append(
            MovementSnapshot(
                movement_id=row.id,
                product_id=row.product_id,
                sku=product.sku if product else "",
                product_name=product.name if product else "",
                location_id=row.location_id,
                movement_type=row.movement_type,
                quantity=row.quantity,
                occurred_at=row.occurred_at,
                reason=row.reason,
                note=row.note,
            )
        )

    cover_rows: list[ProductCoverSnapshot] = []
    demand_rows: list[DemandSnapshot] = []
    forecast_map: dict[str, Decimal] = {}
    contexts: dict[str, PlaybookContext] = {}
    for product in products:
        forecast = forecast_by_id.get(product.id, {})
        daily = Decimal(str(forecast.get("daily_average") or 0))
        forecast_units = Decimal(str(forecast.get("forecast_units") or 0))
        forecast_map[product.id] = forecast_units
        loc_map = loc_on_hand.get(product.id, {})
        cover = ProductCoverSnapshot(
            product_id=product.id,
            sku=product.sku,
            product_name=product.name,
            on_hand=product_on_hand.get(product.id, _ZERO),
            daily_demand=daily,
            lead_time_days=_lead_time(links_by_product.get(product.id, [])),
            location_on_hand=dict(loc_map),
        )
        cover_rows.append(cover)
        series = history_by_id.get(product.id, [])
        last_7 = sum(series[-7:], _ZERO) if series else _ZERO
        prior_7 = sum(series[-14:-7], _ZERO) if len(series) >= 14 else _q_days(daily, 7)
        prior = _week_buckets(series[:-7] if len(series) > 7 else [])
        demand_rows.append(
            DemandSnapshot(
                product_id=product.id,
                sku=product.sku,
                product_name=product.name,
                last_7_units=last_7,
                forecast_7_units=prior_7,
                prior_week_totals=tuple(prior),
            )
        )
        ctx = PlaybookContext(
            supplier_count=len(links_by_product.get(product.id, [])),
            has_open_po=product.id in open_po_products,
            other_location_has_stock=sum(1 for qty in loc_map.values() if qty > 0) >= 2,
            other_location_is_low=location_low.get(product.id, False) and len(loc_map) >= 2,
        )
        contexts[f"stockout_risk:{product.id}"] = ctx
        contexts[f"overstock:{product.id}"] = ctx
        contexts[f"demand_spike:{product.id}"] = ctx
        contexts[f"demand_drop:{product.id}"] = ctx
        contexts[f"data_anomaly:negative_stock:{product.id}"] = ctx

    delay_ctx_by_supplier: dict[str, PlaybookContext] = {}
    for order in orders:
        alt = 0
        for product_id in order.product_ids:
            alt = max(alt, len(links_by_product.get(product_id, [])))
        ctx = PlaybookContext(
            supplier_count=alt,
            has_open_po=True,
            other_location_has_stock=False,
            other_location_is_low=False,
        )
        contexts[f"supplier_delay:{order.po_id}"] = ctx
        delay_ctx_by_supplier[order.supplier_id] = ctx
    for supplier in suppliers:
        contexts[f"supplier_delay:reliability:{supplier.supplier_id}"] = delay_ctx_by_supplier.get(
            supplier.supplier_id,
            PlaybookContext(
                supplier_count=1,
                has_open_po=supplier.overdue_count > 0,
                other_location_has_stock=False,
                other_location_is_low=False,
            ),
        )
    rules = get_autonomy_rules(session, business_id=business_id)
    followup_days = int(rules.get("chase_followup_days") or 3)
    unanswered = list_unanswered_chases(
        session,
        business_id=business_id,
        older_than_days=followup_days,
    )
    chases: list[ChaseFollowupSnapshot] = []
    for message in unanswered:
        supplier = next((item for item in suppliers if item.supplier_id == message.supplier_id), None)
        sent_at = message.sent_at or utcnow()
        days_waiting = max(0, (today - sent_at.date()).days)
        po_number = ""
        if isinstance(message.facts, dict):
            po_number = str(message.facts.get("po_number") or "")
        chases.append(
            ChaseFollowupSnapshot(
                message_id=message.id,
                supplier_id=message.supplier_id,
                supplier_name=supplier.supplier_name if supplier else "",
                po_id=message.po_id,
                po_number=po_number,
                sent_at=sent_at,
                days_waiting=days_waiting,
            )
        )
        contexts[f"chase_no_reply:{message.id}"] = PlaybookContext(
            supplier_count=1,
            has_open_po=message.po_id is not None,
            other_location_has_stock=False,
            other_location_is_low=False,
        )
    forecast_meta: dict[str, object] = {
        "horizon_days": listed.get("horizon_days"),
        "by_product": forecast_by_id,
    }
    return cover_rows, demand_rows, orders, suppliers, movements, forecast_map, chases, contexts, forecast_meta


def _lead_time(links: list[ProductSupplier]) -> int:
    if not links:
        return DEFAULT_LEAD_TIME_DAYS
    preferred = next((row for row in links if row.is_preferred), None)
    chosen = preferred or min(links, key=lambda row: row.lead_time_days)
    return chosen.lead_time_days if chosen.lead_time_days > 0 else DEFAULT_LEAD_TIME_DAYS


def _week_buckets(values: list[Decimal]) -> list[Decimal]:
    buckets: list[Decimal] = []
    for index in range(0, len(values), 7):
        chunk = values[index : index + 7]
        if len(chunk) < 7:
            break
        buckets.append(sum(chunk, _ZERO))
    return buckets


def _q_days(daily: Decimal, days: int) -> Decimal:
    return daily * Decimal(days)


def _as_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value)
    if not text:
        return None
    return date.fromisoformat(text[:10])


def _finding_dict(finding: DetectorFinding, forecast_meta: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "exception_type": finding.exception_type,
        "severity": finding.severity,
        "title": finding.title,
        "entity_type": finding.entity_type,
        "entity_id": finding.entity_id,
        "dedupe_key": finding.dedupe_key,
        "evidence": jsonable(_enrich_evidence(finding, forecast_meta or {})),
    }


def _enrich_evidence(finding: DetectorFinding, forecast_meta: dict[str, object]) -> dict[str, object]:
    evidence = dict(finding.evidence or {})
    evidence.setdefault("reason_codes", [finding.exception_type])
    by_product = forecast_meta.get("by_product")
    if finding.entity_type == "product" and isinstance(by_product, dict):
        forecast = by_product.get(finding.entity_id)
        if isinstance(forecast, dict):
            evidence.setdefault("forecast_method", forecast.get("method"))
            evidence.setdefault("chosen_model", forecast.get("method"))
            if evidence.get("forecast_units") is None and forecast.get("forecast_units") is not None:
                evidence["forecast_units"] = forecast["forecast_units"]
            evidence.setdefault("daily_average", forecast.get("daily_average"))
            evidence.setdefault("horizon_days", forecast_meta.get("horizon_days"))
            evidence.setdefault("history_units", forecast.get("history_units"))
    return evidence


def _empty_ctx() -> PlaybookContext:
    return PlaybookContext(
        supplier_count=0,
        has_open_po=False,
        other_location_has_stock=False,
        other_location_is_low=False,
    )
