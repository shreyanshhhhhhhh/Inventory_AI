"""Backtest and model pick for the forecast agent. No writes. No LLM arithmetic."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from sqlalchemy.orm import Session

from app.services.forecast import (
    HORIZON_DAYS,
    SEASON_LENGTH,
    get_history,
)

_QUANTUM = Decimal("0.0001")
_ONE = Decimal("1")
_ZERO = Decimal("0")

HOLD_OUT_DAYS = 7
TREND_BAND = Decimal("0.10")
LOW_HISTORY_SPAN_DAYS = 14
INTERMITTENT_ZERO_SHARE = Decimal("0.60")
HIGH_WAPE = Decimal("0.40")

Trend = Literal["up", "down", "flat"]
Confidence = Literal["high", "medium", "low"]
ChosenModel = Literal["no_sales", "daily_average", "seasonal_naive"]


@dataclass(frozen=True)
class ForecastEval:
    product_id: str
    sku: str
    product_name: str
    history_units: Decimal
    forecast_units: Decimal
    daily_average: Decimal
    horizon_days: int
    trend: Trend
    chosen_model: ChosenModel
    backtest_wape: Decimal | None
    naive_wape: Decimal | None
    confidence: Confidence
    caveats: tuple[str, ...]
    history_span_days: int
    forecast: tuple[tuple[date, Decimal], ...]


def evaluate_series(
    history: list[tuple[date, Decimal]],
    *,
    product_id: str,
    sku: str,
    product_name: str,
    horizon_days: int = HORIZON_DAYS,
) -> ForecastEval:
    """Pick a model from a backtest. Quantities stay Decimal."""
    history_units = _q(sum((units for _, units in history), _ZERO))
    span_days = _span_days(history)
    caveats = _caveats(history, span_days=span_days, history_units=history_units)
    trend = _trend(history)
    if history_units == 0:
        chosen: ChosenModel = "no_sales"
        backtest_wape = None
        naive_wape = None
    else:
        backtest_wape, naive_wape, chosen = _backtest(history)
    points = _project_model(history, model=chosen, horizon_days=horizon_days)
    forecast_units = _q(sum((units for _, units in points), _ZERO))
    daily_average = _q(forecast_units / Decimal(horizon_days)) if horizon_days else _ZERO
    confidence = _confidence(
        caveats=caveats,
        backtest_wape=backtest_wape,
        naive_wape=naive_wape,
        span_days=span_days,
    )
    return ForecastEval(
        product_id=product_id,
        sku=sku,
        product_name=product_name,
        history_units=history_units,
        forecast_units=forecast_units,
        daily_average=daily_average,
        horizon_days=horizon_days,
        trend=trend,
        chosen_model=chosen,
        backtest_wape=backtest_wape,
        naive_wape=naive_wape,
        confidence=confidence,
        caveats=caveats,
        history_span_days=span_days,
        forecast=tuple(points),
    )


def run_forecast(
    session: Session,
    *,
    business_id: str,
    product_id: str | None = None,
) -> dict[str, object]:
    raw = get_history(session, business_id=business_id, product_id=product_id)
    items = [_eval_from_history_item(item) for item in raw["items"]]  # type: ignore[arg-type]
    return {
        "history_days": raw["history_days"],
        "horizon_days": HORIZON_DAYS,
        "items": [eval_to_dict(item) for item in items],
    }


def get_forecast_accuracy(
    session: Session,
    *,
    business_id: str,
    product_id: str | None = None,
) -> dict[str, object]:
    raw = run_forecast(session, business_id=business_id, product_id=product_id)
    items = []
    for item in raw["items"]:  # type: ignore[union-attr]
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "product_id": item["product_id"],
                "sku": item["sku"],
                "product_name": item["product_name"],
                "chosen_model": item["chosen_model"],
                "backtest_wape": item["backtest_wape"],
                "naive_wape": item["naive_wape"],
                "confidence": item["confidence"],
                "caveats": item["caveats"],
            }
        )
    return {"items": items}


def eval_to_dict(item: ForecastEval) -> dict[str, object]:
    return {
        "product_id": item.product_id,
        "sku": item.sku,
        "product_name": item.product_name,
        "history_units": item.history_units,
        "forecast_units": item.forecast_units,
        "daily_average": item.daily_average,
        "horizon_days": item.horizon_days,
        "trend": item.trend,
        "chosen_model": item.chosen_model,
        "backtest_wape": item.backtest_wape,
        "naive_wape": item.naive_wape,
        "confidence": item.confidence,
        "caveats": list(item.caveats),
        "history_span_days": item.history_span_days,
        "forecast": [{"date": day, "units": units} for day, units in item.forecast],
    }


def _eval_from_history_item(item: dict[str, object]) -> ForecastEval:
    series_raw = item.get("history")
    series: list[tuple[date, Decimal]] = []
    if isinstance(series_raw, list):
        for point in series_raw:
            if not isinstance(point, dict):
                continue
            day = point.get("date")
            units = point.get("units")
            if day is None or units is None:
                continue
            series.append((_as_date(day), _q(Decimal(str(units)))))
    return evaluate_series(
        series,
        product_id=str(item["product_id"]),
        sku=str(item["sku"]),
        product_name=str(item["product_name"]),
    )


def _as_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _q(value: Decimal) -> Decimal:
    return value.quantize(_QUANTUM, rounding=ROUND_HALF_UP)


def _span_days(history: list[tuple[date, Decimal]]) -> int:
    first = next((day for day, units in history if units > 0), None)
    if first is None or not history:
        return 0
    return (history[-1][0] - first).days + 1


def _caveats(
    history: list[tuple[date, Decimal]],
    *,
    span_days: int,
    history_units: Decimal,
) -> tuple[str, ...]:
    found: list[str] = []
    if span_days < LOW_HISTORY_SPAN_DAYS:
        found.append("low_history")
    if history and history_units > 0:
        zeros = sum(1 for _day, units in history if units == 0)
        share = Decimal(zeros) / Decimal(len(history))
        if share >= INTERMITTENT_ZERO_SHARE:
            found.append("intermittent_demand")
    return tuple(found)


def _trend(history: list[tuple[date, Decimal]]) -> Trend:
    if len(history) < 14:
        last = sum((units for _, units in history[-7:]), _ZERO)
        if last > 0 and len(history) >= 7:
            return "up"
        return "flat"
    last7 = sum((units for _, units in history[-7:]), _ZERO)
    prev7 = sum((units for _, units in history[-14:-7]), _ZERO)
    if prev7 == 0:
        if last7 > 0:
            return "up"
        return "flat"
    ratio = last7 / prev7
    if ratio >= _ONE + TREND_BAND:
        return "up"
    if ratio <= _ONE - TREND_BAND:
        return "down"
    return "flat"


def _wape(actual: list[Decimal], predicted: list[Decimal]) -> Decimal:
    denom = sum((abs(value) for value in actual), _ZERO)
    numer = sum((abs(a - p) for a, p in zip(actual, predicted, strict=True)), _ZERO)
    if denom == 0:
        return _ZERO if numer == 0 else _ONE
    return _q(numer / denom)


def _last_value_forecast(train: list[Decimal], horizon: int) -> list[Decimal]:
    last = train[-1] if train else _ZERO
    return [last] * horizon


def _daily_average_forecast(train: list[Decimal], horizon: int) -> list[Decimal]:
    if not train:
        return [_ZERO] * horizon
    nonzero_span = len(train)
    first = next((index for index, units in enumerate(train) if units > 0), None)
    if first is not None:
        nonzero_span = len(train) - first
    total = sum(train, _ZERO)
    if nonzero_span <= 0:
        return [_ZERO] * horizon
    average = _q(total / Decimal(nonzero_span))
    return [average] * horizon


def _seasonal_naive_forecast(train: list[Decimal], horizon: int) -> list[Decimal] | None:
    if len(train) < SEASON_LENGTH:
        return None
    last_week = train[-SEASON_LENGTH:]
    return [last_week[index % SEASON_LENGTH] for index in range(horizon)]


def _backtest(history: list[tuple[date, Decimal]]) -> tuple[Decimal | None, Decimal | None, ChosenModel]:
    hold = min(HOLD_OUT_DAYS, max(1, len(history) // 4))
    if len(history) < hold + SEASON_LENGTH:
        return None, None, "daily_average"
    train_rows = history[:-hold]
    hold_rows = history[-hold:]
    train = [units for _, units in train_rows]
    actual = [units for _, units in hold_rows]
    naive = _wape(actual, _last_value_forecast(train, hold))
    daily = _wape(actual, _daily_average_forecast(train, hold))
    seasonal_points = _seasonal_naive_forecast(train, hold)
    best_model: ChosenModel = "daily_average"
    best_wape = daily
    if seasonal_points is not None:
        seasonal = _wape(actual, seasonal_points)
        if seasonal < best_wape:
            best_model = "seasonal_naive"
            best_wape = seasonal
    return best_wape, naive, best_model


def _project_model(
    history: list[tuple[date, Decimal]],
    *,
    model: ChosenModel,
    horizon_days: int,
) -> list[tuple[date, Decimal]]:
    today = history[-1][0] if history else date.today()
    future = [today + timedelta(days=offset) for offset in range(1, horizon_days + 1)]
    units = [value for _, value in history]
    if model == "no_sales" or not units:
        return [(day, _ZERO) for day in future]
    if model == "seasonal_naive":
        points = _seasonal_naive_forecast(units, horizon_days)
        if points is None:
            points = _daily_average_forecast(units, horizon_days)
        return [(day, _q(value)) for day, value in zip(future, points, strict=True)]
    points = _daily_average_forecast(units, horizon_days)
    return [(day, _q(value)) for day, value in zip(future, points, strict=True)]


def _confidence(
    *,
    caveats: tuple[str, ...],
    backtest_wape: Decimal | None,
    naive_wape: Decimal | None,
    span_days: int,
) -> Confidence:
    if "low_history" in caveats or "intermittent_demand" in caveats or backtest_wape is None:
        return "low"
    beats_naive = naive_wape is None or backtest_wape <= naive_wape
    if span_days >= 28 and beats_naive and backtest_wape <= HIGH_WAPE:
        return "high"
    return "medium"
