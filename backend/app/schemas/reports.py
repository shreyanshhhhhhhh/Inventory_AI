from datetime import date
from decimal import Decimal

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
