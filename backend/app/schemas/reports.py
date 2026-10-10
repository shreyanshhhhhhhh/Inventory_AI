from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_serializer

from app.schemas.inventory import _serialize_decimal


class MovementsOverTimePointResponse(BaseModel):
    date: date
    units_in: Decimal
    units_out: Decimal

    @field_serializer("units_in", "units_out")
    def serialize_units(self, value: Decimal) -> str:
        return _serialize_decimal(value) or "0"


class MovementsOverTimeResponse(BaseModel):
    days: int
    items: list[MovementsOverTimePointResponse]


class TopSellerResponse(BaseModel):
    product_id: str
    product_name: str
    units_sold: Decimal

    @field_serializer("units_sold")
    def serialize_units_sold(self, value: Decimal) -> str:
        return _serialize_decimal(value) or "0"


class TopSellersResponse(BaseModel):
    days: int
    limit: int
    items: list[TopSellerResponse]


class AccountsSummaryResponse(BaseModel):
    stock_value: Decimal
    unvalued_product_count: int = 0
    open_po_value: Decimal
    payables_due: Decimal

    @field_serializer("stock_value", "open_po_value", "payables_due")
    def serialize_money(self, value: Decimal) -> str:
        return _serialize_decimal(value) or "0"


class AccountsBySupplierRowResponse(BaseModel):
    supplier_id: str
    supplier_name: str
    status: str
    total: Decimal
    purchase_order_count: int

    @field_serializer("total")
    def serialize_total(self, value: Decimal) -> str:
        return _serialize_decimal(value) or "0"


class AccountsBySupplierResponse(BaseModel):
    items: list[AccountsBySupplierRowResponse] = Field(default_factory=list)


ForecastMethod = Literal["seasonal_naive", "daily_average", "no_sales"]


class DemandPointResponse(BaseModel):
    date: date
    units: Decimal

    @field_serializer("units")
    def serialize_units(self, value: Decimal) -> str:
        return _serialize_decimal(value) or "0"


class ForecastSummaryResponse(BaseModel):
    product_id: str
    sku: str
    product_name: str
    history_units: Decimal
    forecast_units: Decimal
    daily_average: Decimal
    method: ForecastMethod

    @field_serializer("history_units", "forecast_units", "daily_average")
    def serialize_quantities(self, value: Decimal) -> str:
        return _serialize_decimal(value) or "0"


class ForecastListResponse(BaseModel):
    history_days: int
    horizon_days: int
    items: list[ForecastSummaryResponse]


class ForecastDetailResponse(ForecastSummaryResponse):
    history_days: int
    horizon_days: int
    history: list[DemandPointResponse]
    forecast: list[DemandPointResponse]
