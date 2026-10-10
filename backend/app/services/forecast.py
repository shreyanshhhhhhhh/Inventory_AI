"""Demand forecasts computed from sale movements. Nothing here writes stock or orders."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Product, StockMovement
from app.models.types import utcnow

HISTORY_DAYS = 56
HORIZON_DAYS = 14
SEASON_LENGTH = 7
_QUANTUM = Decimal("0.0001")


class ForecastError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, code: str = "bad_request") -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


def list_forecasts(
    session: Session,
    *,
    business_id: str,
    history_days: int = HISTORY_DAYS,
    horizon_days: int = HORIZON_DAYS,
) -> dict[str, object]:
    history_days, horizon_days = _validate_window(history_days, horizon_days)
    start, end, day_list = _window(history_days)
    products = _active_products(session, business_id)
    totals = _sale_totals(
        session,
        business_id=business_id,
        start=start,
        end=end,
        product_id=None,
    )
    items = [
        _forecast_item(
            product,
            totals.get(product.id, {}),
            day_list=day_list,
            horizon_days=horizon_days,
            include_series=False,
        )
        for product in products
    ]
    items.sort(key=lambda item: (-item["forecast_units"], str(item["product_name"]).lower()))
    return {
        "history_days": history_days,
        "horizon_days": horizon_days,
        "items": items,
    }


def get_forecast(
    session: Session,
    *,
    business_id: str,
    product_id: str,
    history_days: int = HISTORY_DAYS,
    horizon_days: int = HORIZON_DAYS,
) -> dict[str, object]:
    history_days, horizon_days = _validate_window(history_days, horizon_days)
    product = session.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.business_id == business_id,
            Product.archived_at.is_(None),
        )
    )
    if product is None:
        raise ForecastError("Product not found.", status_code=404, code="not_found")

    start, end, day_list = _window(history_days)
    totals = _sale_totals(
        session,
        business_id=business_id,
        start=start,
        end=end,
        product_id=product.id,
    )
    item = _forecast_item(
        product,
        totals.get(product.id, {}),
        day_list=day_list,
        horizon_days=horizon_days,
        include_series=True,
    )
    return {
        "history_days": history_days,
        "horizon_days": horizon_days,
        **item,
    }


def get_history(
    session: Session,
    *,
    business_id: str,
    product_id: str | None = None,
    history_days: int = HISTORY_DAYS,
) -> dict[str, object]:
    history_days, _horizon = _validate_window(history_days, HORIZON_DAYS)
    start, end, day_list = _window(history_days)
    if product_id is None:
        products = _active_products(session, business_id)
    else:
        product = session.scalar(
            select(Product).where(
                Product.id == product_id,
                Product.business_id == business_id,
                Product.archived_at.is_(None),
            )
        )
        if product is None:
            raise ForecastError("Product not found.", status_code=404, code="not_found")
        products = [product]
    totals = _sale_totals(
        session,
        business_id=business_id,
        start=start,
        end=end,
        product_id=product_id,
    )
    items = [
        _history_item(product, totals.get(product.id, {}), day_list=day_list)
        for product in products
    ]
    return {"history_days": history_days, "items": items}


def _validate_window(history_days: int, horizon_days: int) -> tuple[int, int]:
    if history_days < SEASON_LENGTH or history_days > 180:
        raise ForecastError("History window must be between 7 and 180 days.")
    if horizon_days < 1 or horizon_days > 30:
        raise ForecastError("Forecast horizon must be between 1 and 30 days.")
    return history_days, horizon_days


def _window(history_days: int) -> tuple[datetime, datetime, list[date]]:
    today = utcnow().astimezone(timezone.utc).date()
    start_day = today - timedelta(days=history_days - 1)
    start = datetime.combine(start_day, time.min, tzinfo=timezone.utc)
    end = datetime.combine(today, time.max, tzinfo=timezone.utc)
    day_list = [start_day + timedelta(days=offset) for offset in range(history_days)]
    return start, end, day_list


def _active_products(session: Session, business_id: str) -> list[Product]:
    return list(
        session.scalars(
            select(Product)
            .where(
                Product.business_id == business_id,
                Product.archived_at.is_(None),
            )
            .order_by(Product.name.asc())
        ).all()
    )


def _sale_totals(
    session: Session,
    *,
    business_id: str,
    start: datetime,
    end: datetime,
    product_id: str | None,
) -> dict[str, dict[date, Decimal]]:
    sale_day = func.date(StockMovement.occurred_at)
    query = (
        select(
            StockMovement.product_id.label("product_id"),
            sale_day.label("day"),
            func.coalesce(func.sum(-StockMovement.quantity), 0).label("units"),
        )
        .where(
            StockMovement.business_id == business_id,
            StockMovement.movement_type == "sale",
            StockMovement.occurred_at >= start,
            StockMovement.occurred_at <= end,
        )
        .group_by(StockMovement.product_id, sale_day)
    )
    if product_id is not None:
        query = query.where(StockMovement.product_id == product_id)

    totals: dict[str, dict[date, Decimal]] = {}
    for row in session.execute(query).all():
        day = _as_date(row.day)
        by_day = totals.setdefault(row.product_id, {})
        by_day[day] = _q(Decimal(row.units))
    return totals


def _forecast_item(
    product: Product,
    units_by_day: dict[date, Decimal],
    *,
    day_list: list[date],
    horizon_days: int,
    include_series: bool,
) -> dict[str, object]:
    history = [(day, _q(units_by_day.get(day, Decimal("0")))) for day in day_list]
    history_units = _q(sum((units for _, units in history), Decimal("0")))
    method, forecast_points = _project(history, horizon_days=horizon_days, history_units=history_units)
    forecast_units = _q(sum((units for _, units in forecast_points), Decimal("0")))
    if horizon_days == 0:
        daily_average = Decimal("0")
    else:
        daily_average = _q(forecast_units / Decimal(horizon_days))

    item: dict[str, object] = {
        "product_id": product.id,
        "sku": product.sku,
        "product_name": product.name,
        "history_units": history_units,
        "forecast_units": forecast_units,
        "daily_average": daily_average,
        "method": method,
    }
    if include_series:
        item["history"] = [{"date": day, "units": units} for day, units in history]
        item["forecast"] = [{"date": day, "units": units} for day, units in forecast_points]
    return item


def _history_item(
    product: Product,
    units_by_day: dict[date, Decimal],
    *,
    day_list: list[date],
) -> dict[str, object]:
    history = [(day, _q(units_by_day.get(day, Decimal("0")))) for day in day_list]
    history_units = _q(sum((units for _, units in history), Decimal("0")))
    return {
        "product_id": product.id,
        "sku": product.sku,
        "product_name": product.name,
        "history_units": history_units,
        "history": [{"date": day, "units": units} for day, units in history],
    }


def _project(
    history: list[tuple[date, Decimal]],
    *,
    horizon_days: int,
    history_units: Decimal,
) -> tuple[str, list[tuple[date, Decimal]]]:
    today = history[-1][0]
    future_days = [today + timedelta(days=offset) for offset in range(1, horizon_days + 1)]
    if history_units == 0:
        return "no_sales", [(day, Decimal("0")) for day in future_days]

    first_sale = next(day for day, units in history if units > 0)
    span_days = (today - first_sale).days + 1
    if span_days < SEASON_LENGTH:
        average = _q(history_units / Decimal(span_days))
        return "daily_average", [(day, average) for day in future_days]

    last_week = [units for _, units in history[-SEASON_LENGTH:]]
    forecast = [
        (day, last_week[(offset - 1) % SEASON_LENGTH])
        for offset, day in enumerate(future_days, start=1)
    ]
    return "seasonal_naive", forecast


def _as_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _q(value: Decimal) -> Decimal:
    return value.quantize(_QUANTUM, rounding=ROUND_HALF_UP)
