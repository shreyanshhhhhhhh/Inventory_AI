from datetime import date, datetime, timezone
from decimal import Decimal

from app.agents.playbooks import PlaybookContext, candidate_actions, clip_action
from app.services.detectors import (
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


def _cover(
    *,
    product_id: str = "p1",
    sku: str = "SKU-1",
    on_hand: str = "10",
    daily: str = "1",
    lead: int = 7,
    locations: dict[str, str] | None = None,
) -> ProductCoverSnapshot:
    loc = locations or {"loc-a": on_hand}
    return ProductCoverSnapshot(
        product_id=product_id,
        sku=sku,
        product_name=sku,
        on_hand=Decimal(on_hand),
        daily_demand=Decimal(daily),
        lead_time_days=lead,
        location_on_hand={key: Decimal(value) for key, value in loc.items()},
    )


def test_stockout_risk_true_positive_and_clean_negative() -> None:
    at_risk = detect_stockout_risk([_cover(on_hand="4", daily="2", lead=7)])
    assert len(at_risk) == 1
    assert at_risk[0].exception_type == "stockout_risk"
    assert at_risk[0].dedupe_key == "stockout_risk:p1"
    assert at_risk[0].evidence["days_of_cover"] == Decimal("2.0000")
    critical = detect_stockout_risk([_cover(on_hand="0", daily="1")])
    assert critical[0].severity == "critical"
    clean = detect_stockout_risk([_cover(on_hand="40", daily="1", lead=7)])
    assert clean == []
    no_demand = detect_stockout_risk([_cover(on_hand="0", daily="0")])
    assert no_demand == []


def test_overstock_true_positive_and_clean_negative() -> None:
    high = detect_overstock([_cover(on_hand="400", daily="1")])
    assert len(high) == 1
    assert high[0].severity == "high"
    medium = detect_overstock([_cover(on_hand="120", daily="1")])
    assert medium[0].severity == "medium"
    clean = detect_overstock([_cover(on_hand="20", daily="1")])
    assert clean == []
    unsold = detect_overstock([_cover(on_hand="500", daily="0")])
    assert unsold == []


def test_demand_spike_and_drop_versus_clean_series() -> None:
    spike = detect_demand_shift(
        [
            DemandSnapshot(
                product_id="p1",
                sku="SPIKE",
                product_name="Spike",
                last_7_units=Decimal("70"),
                forecast_7_units=Decimal("7"),
                prior_week_totals=(Decimal("7"), Decimal("7"), Decimal("8"), Decimal("6")),
            )
        ]
    )
    assert spike[0].exception_type == "demand_spike"
    drop = detect_demand_shift(
        [
            DemandSnapshot(
                product_id="p2",
                sku="DROP",
                product_name="Drop",
                last_7_units=Decimal("3"),
                forecast_7_units=Decimal("70"),
                prior_week_totals=(Decimal("70"), Decimal("68"), Decimal("72"), Decimal("71")),
            )
        ]
    )
    assert drop[0].exception_type == "demand_drop"
    clean = detect_demand_shift(
        [
            DemandSnapshot(
                product_id="p3",
                sku="OK",
                product_name="Ok",
                last_7_units=Decimal("14"),
                forecast_7_units=Decimal("14"),
                prior_week_totals=(Decimal("14"), Decimal("13"), Decimal("15"), Decimal("14")),
            )
        ]
    )
    assert clean == []
    quiet = detect_demand_shift(
        [
            DemandSnapshot(
                product_id="p4",
                sku="QUIET",
                product_name="Quiet",
                last_7_units=Decimal("0"),
                forecast_7_units=Decimal("0"),
                prior_week_totals=(Decimal("0"), Decimal("0"), Decimal("0")),
            )
        ]
    )
    assert quiet == []


def test_supplier_delay_overdue_po_and_degrading_reliability() -> None:
    today = date(2026, 10, 6)
    overdue = detect_supplier_delay(
        [
            PurchaseOrderSnapshot(
                po_id="po1",
                po_number="PO-1",
                supplier_id="s1",
                supplier_name="Acme",
                status="sent",
                expected_on=date(2026, 10, 1),
                product_ids=("p1",),
            )
        ],
        [
            SupplierReliabilitySnapshot(
                supplier_id="s1",
                supplier_name="Acme",
                reliability_score=0.4,
                overdue_count=2,
            )
        ],
        today=today,
    )
    types = {item.dedupe_key.split(":")[0] for item in overdue}
    assert "supplier_delay" in {item.exception_type for item in overdue}
    assert any(item.entity_type == "purchase_order" for item in overdue)
    assert any(item.entity_type == "supplier" for item in overdue)
    del types
    clean = detect_supplier_delay(
        [
            PurchaseOrderSnapshot(
                po_id="po2",
                po_number="PO-2",
                supplier_id="s2",
                supplier_name="On Time",
                status="sent",
                expected_on=date(2026, 10, 20),
                product_ids=("p1",),
            )
        ],
        [
            SupplierReliabilitySnapshot(
                supplier_id="s2",
                supplier_name="On Time",
                reliability_score=1.0,
                overdue_count=0,
            )
        ],
        today=today,
    )
    assert clean == []


def test_data_anomaly_negative_duplicate_and_unreconciled() -> None:
    stock = [
        _cover(
            on_hand="-3",
            daily="1",
            locations={"loc-a": "-3"},
        )
    ]
    when = datetime(2026, 10, 5, 12, 1, tzinfo=timezone.utc)
    movements = [
        MovementSnapshot(
            movement_id="m1",
            product_id="p1",
            sku="SKU-1",
            product_name="SKU-1",
            location_id="loc-a",
            movement_type="sale",
            quantity=Decimal("-2"),
            occurred_at=when,
            reason=None,
            note=None,
        ),
        MovementSnapshot(
            movement_id="m2",
            product_id="p1",
            sku="SKU-1",
            product_name="SKU-1",
            location_id="loc-a",
            movement_type="sale",
            quantity=Decimal("-2"),
            occurred_at=when.replace(second=30),
            reason=None,
            note=None,
        ),
        MovementSnapshot(
            movement_id="m3",
            product_id="p1",
            sku="SKU-1",
            product_name="SKU-1",
            location_id="loc-a",
            movement_type="adjustment",
            quantity=Decimal("250"),
            occurred_at=when,
            reason="Count",
            note="Count",
        ),
    ]
    findings = detect_data_anomaly(stock, movements, {"p1": Decimal("0")})
    kinds = {item.dedupe_key.split(":")[1] for item in findings}
    assert "negative_stock" in kinds
    assert "duplicate_sales" in kinds
    assert "unreconciled_adjustment" in kinds
    clean = detect_data_anomaly(
        [_cover(on_hand="10", daily="1", locations={"loc-a": "10"})],
        [
            MovementSnapshot(
                movement_id="m9",
                product_id="p1",
                sku="SKU-1",
                product_name="SKU-1",
                location_id="loc-a",
                movement_type="sale",
                quantity=Decimal("-1"),
                occurred_at=when,
                reason=None,
                note=None,
            )
        ],
        {"p1": Decimal("14")},
    )
    assert clean == []


def test_playbook_filters_preconditions_and_clips_unknown_actions() -> None:
    finding = DetectorFinding(
        exception_type="stockout_risk",
        severity="high",
        title="out",
        entity_type="product",
        entity_id="p1",
        dedupe_key="stockout_risk:p1",
        evidence={},
    )
    none_allowed = candidate_actions(
        finding,
        PlaybookContext(
            supplier_count=0,
            has_open_po=False,
            other_location_has_stock=False,
            other_location_is_low=False,
        ),
    )
    assert none_allowed == ["ignore"]
    with_supplier = candidate_actions(
        finding,
        PlaybookContext(
            supplier_count=2,
            has_open_po=True,
            other_location_has_stock=True,
            other_location_is_low=False,
        ),
    )
    assert with_supplier[0] == "reorder_now"
    assert "alternate_supplier" in with_supplier
    assert "expedite" in with_supplier
    assert clip_action("hack_the_ledger", with_supplier) == "reorder_now"
    assert clip_action("expedite", with_supplier) == "expedite"


def test_chase_no_reply_is_low_severity() -> None:
    findings = detect_chase_no_reply(
        [
            ChaseFollowupSnapshot(
                message_id="m1",
                supplier_id="s1",
                supplier_name="Mill",
                po_id="po1",
                po_number="PO-0001",
                sent_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
                days_waiting=4,
            )
        ]
    )
    assert len(findings) == 1
    assert findings[0].exception_type == "chase_no_reply"
    assert findings[0].severity == "low"
    assert findings[0].dedupe_key == "chase_no_reply:m1"
    finding = DetectorFinding(
        exception_type="chase_no_reply",
        severity="low",
        title="chase",
        entity_type="supplier_message",
        entity_id="m1",
        dedupe_key="chase_no_reply:m1",
        evidence={},
    )
    assert candidate_actions(
        finding,
        PlaybookContext(
            supplier_count=1,
            has_open_po=True,
            other_location_has_stock=False,
            other_location_is_low=False,
        ),
    ) == ["ignore"]
