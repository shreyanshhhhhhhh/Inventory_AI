from datetime import date, timedelta
from decimal import Decimal

from app.services.forecast_eval import evaluate_series


def _series(values: list[str], *, start: date | None = None) -> list[tuple[date, Decimal]]:
    day = start or date(2026, 8, 1)
    rows: list[tuple[date, Decimal]] = []
    for index, raw in enumerate(values):
        rows.append((day + timedelta(days=index), Decimal(raw)))
    return rows


def test_no_sales_is_low_confidence_no_sales_model() -> None:
    history = _series(["0"] * 56)
    result = evaluate_series(
        history,
        product_id="p1",
        sku="ZERO",
        product_name="Zero",
    )
    assert result.chosen_model == "no_sales"
    assert result.forecast_units == Decimal("0.0000")
    assert result.backtest_wape is None
    assert result.confidence == "low"
    assert "low_history" in result.caveats


def test_short_history_flags_low_history_and_uses_daily_average() -> None:
    history = _series(["0"] * 50 + ["2", "2", "2", "2", "2", "2"])
    result = evaluate_series(
        history,
        product_id="p1",
        sku="SHORT",
        product_name="Short",
    )
    assert result.chosen_model in {"daily_average", "seasonal_naive"}
    assert "low_history" in result.caveats
    assert result.confidence == "low"
    assert result.trend in {"up", "flat"}


def test_steady_weekly_pattern_picks_a_model_and_reports_wape() -> None:
    week = ["4", "4", "4", "4", "4", "1", "1"]
    history = _series(week * 8)
    result = evaluate_series(
        history,
        product_id="p1",
        sku="STEADY",
        product_name="Steady",
    )
    assert result.chosen_model in {"daily_average", "seasonal_naive"}
    assert result.backtest_wape is not None
    assert result.naive_wape is not None
    assert result.horizon_days == 14
    assert len(result.forecast) == 14
    assert "low_history" not in result.caveats


def test_intermittent_demand_is_a_caveat() -> None:
    values = (["3"] + ["0"] * 6) * 8
    result = evaluate_series(
        _series(values),
        product_id="p1",
        sku="SPARSE",
        product_name="Sparse",
    )
    assert "intermittent_demand" in result.caveats
    assert result.confidence == "low"
