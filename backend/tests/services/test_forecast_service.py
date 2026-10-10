from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.models import PurchaseOrder, StockMovement
from app.models.types import utcnow
from app.repositories import inventory as inventory_repo
from app.services.auth import signup
from app.services.catalog import archive_product, create_product
from app.services.forecast import ForecastError, get_forecast, list_forecasts
from app.services.inventory import post_movement, record_movement


def _owner(db, *, email: str, business_name: str):
    return signup(
        db,
        full_name="Ada Owner",
        email=email,
        password="correct-horse-1",
        business_name=business_name,
    )


def _location_id(db, business_id: str) -> str:
    return inventory_repo.list_locations(db, business_id)[0].id


def _product(db, *, business_id: str, actor_user_id: str, sku: str, name: str) -> str:
    product = create_product(
        db,
        business_id=business_id,
        actor_user_id=actor_user_id,
        sku=sku,
        name=name,
        category_id=None,
        unit="each",
        cost=Decimal("2.00"),
        price=Decimal("5.00"),
        reorder_point=Decimal("5"),
        safety_stock=Decimal("0"),
        preferred_supplier_id=None,
    )
    return product.id


def _at(day_offset: int) -> datetime:
    today = utcnow().astimezone(timezone.utc).date()
    return datetime.combine(
        today + timedelta(days=day_offset),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )


def _sell(db, *, business_id: str, actor_user_id: str, product_id: str, location_id: str, day_offset: int, quantity: str) -> None:
    post_movement(
        db,
        business_id=business_id,
        actor_user_id=actor_user_id,
        product_id=product_id,
        location_id=location_id,
        movement_type="sale",
        quantity=Decimal(quantity),
        occurred_at=_at(day_offset),
    )


def test_empty_catalog_has_no_forecasts(db) -> None:
    owner = _owner(db, email="forecast-empty@example.com", business_name="Empty Forecast")
    result = list_forecasts(db, business_id=owner.user.business_id)
    assert result["history_days"] == 56
    assert result["horizon_days"] == 14
    assert result["items"] == []


def test_receipts_are_not_demand_and_short_history_uses_daily_average(db) -> None:
    owner = _owner(db, email="forecast-avg@example.com", business_name="Average Shop")
    business_id = owner.user.business_id
    location_id = _location_id(db, business_id)
    product_id = _product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="AVG-1",
        name="Spinach",
    )
    record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_id,
        location_id=location_id,
        movement_type="receipt",
        quantity=Decimal("20"),
        occurred_at=_at(-1),
    )
    _sell(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_id,
        location_id=location_id,
        day_offset=-1,
        quantity="4",
    )
    _sell(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_id,
        location_id=location_id,
        day_offset=0,
        quantity="2",
    )

    item = get_forecast(db, business_id=business_id, product_id=product_id, horizon_days=14)
    assert item["method"] == "daily_average"
    assert item["history_units"] == Decimal("6.0000")
    assert item["daily_average"] == Decimal("3.0000")
    assert item["forecast_units"] == Decimal("42.0000")
    assert [point["units"] for point in item["forecast"]] == [Decimal("3.0000")] * 14


def test_weekly_pattern_repeats_the_last_seven_days(db) -> None:
    owner = _owner(db, email="forecast-week@example.com", business_name="Weekly Shop")
    business_id = owner.user.business_id
    location_id = _location_id(db, business_id)
    product_id = _product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="WEEK-1",
        name="Avocado",
    )
    record_movement(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=product_id,
        location_id=location_id,
        movement_type="receipt",
        quantity=Decimal("200"),
        occurred_at=_at(-13),
    )
    older_week = [Decimal(str(units)) for units in (1, 2, 3, 4, 5, 6, 7)]
    last_week = [Decimal(str(units)) for units in (2, 3, 4, 5, 6, 7, 8)]
    for offset, quantity in zip(range(-13, -6), older_week, strict=True):
        _sell(
            db,
            business_id=business_id,
            actor_user_id=owner.user.id,
            product_id=product_id,
            location_id=location_id,
            day_offset=offset,
            quantity=str(quantity),
        )
    for offset, quantity in zip(range(-6, 1), last_week, strict=True):
        _sell(
            db,
            business_id=business_id,
            actor_user_id=owner.user.id,
            product_id=product_id,
            location_id=location_id,
            day_offset=offset,
            quantity=str(quantity),
        )

    item = get_forecast(db, business_id=business_id, product_id=product_id, horizon_days=14)
    assert item["method"] == "seasonal_naive"
    assert item["history_units"] == Decimal("63.0000")
    assert [point["units"] for point in item["forecast"]] == last_week + last_week
    assert item["forecast_units"] == Decimal("70.0000")


def test_archived_products_are_omitted_and_missing_products_404(db) -> None:
    owner = _owner(db, email="forecast-archive@example.com", business_name="Archive Shop")
    business_id = owner.user.business_id
    kept_id = _product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="KEEP",
        name="Kept",
    )
    archived_id = _product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="GONE",
        name="Gone",
    )
    archive_product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        product_id=archived_id,
    )

    listed = list_forecasts(db, business_id=business_id)
    assert [item["product_id"] for item in listed["items"]] == [kept_id]
    assert listed["items"][0]["method"] == "no_sales"

    try:
        get_forecast(db, business_id=business_id, product_id=archived_id)
    except ForecastError as exc:
        assert exc.status_code == 404
        assert exc.code == "not_found"
    else:
        raise AssertionError("archived product should not forecast")


def test_forecast_reads_do_not_write_orders_or_ledger_rows(db) -> None:
    owner = _owner(db, email="forecast-readonly@example.com", business_name="Read Only")
    business_id = owner.user.business_id
    product_id = _product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="READ-1",
        name="Milk",
    )

    def counts() -> tuple[int, int]:
        orders = db.scalar(
            select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.business_id == business_id)
        )
        movements = db.scalar(
            select(func.count()).select_from(StockMovement).where(StockMovement.business_id == business_id)
        )
        return int(orders or 0), int(movements or 0)

    before = counts()
    list_forecasts(db, business_id=business_id)
    get_forecast(db, business_id=business_id, product_id=product_id)
    assert counts() == before


def test_tenant_isolation(db) -> None:
    owner_a = _owner(db, email="forecast-a@example.com", business_name="Shop A")
    owner_b = _owner(db, email="forecast-b@example.com", business_name="Shop B")
    business_a = owner_a.user.business_id
    business_b = owner_b.user.business_id
    location_a = _location_id(db, business_a)
    product_a = _product(
        db,
        business_id=business_a,
        actor_user_id=owner_a.user.id,
        sku="SHARED-SKU",
        name="Shared name",
    )
    product_b = _product(
        db,
        business_id=business_b,
        actor_user_id=owner_b.user.id,
        sku="SHARED-SKU",
        name="Shared name",
    )
    record_movement(
        db,
        business_id=business_a,
        actor_user_id=owner_a.user.id,
        product_id=product_a,
        location_id=location_a,
        movement_type="receipt",
        quantity=Decimal("10"),
        occurred_at=_at(0),
    )
    _sell(
        db,
        business_id=business_a,
        actor_user_id=owner_a.user.id,
        product_id=product_a,
        location_id=location_a,
        day_offset=0,
        quantity="3",
    )

    other = get_forecast(db, business_id=business_b, product_id=product_b)
    assert other["history_units"] == Decimal("0.0000")
    assert other["method"] == "no_sales"

    try:
        get_forecast(db, business_id=business_b, product_id=product_a)
    except ForecastError as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("other tenant product should be hidden")
