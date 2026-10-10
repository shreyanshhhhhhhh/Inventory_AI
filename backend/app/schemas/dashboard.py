from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_serializer

from app.schemas.inventory import StockStatus, _serialize_decimal


class DashboardSummaryResponse(BaseModel):
    total_stock_value: Decimal
    unvalued_product_count: int = 0
    low_stock_count: int
    open_purchase_orders: int
    pending_approvals: int = 0
    open_exceptions: int = 0

    @field_serializer("total_stock_value")
    def serialize_total_stock_value(self, value: Decimal) -> str:
        return _serialize_decimal(value) or "0"


class NeedsAttentionItemResponse(BaseModel):
    product_id: str
    location_id: str
    sku: str
    product_name: str
    location_name: str
    on_hand: Decimal
    reorder_point: Decimal | None
    status: StockStatus

    @field_serializer("on_hand", "reorder_point")
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        return _serialize_decimal(value)


class NeedsAttentionResponse(BaseModel):
    items: list[NeedsAttentionItemResponse]


ActivityKind = Literal["movement", "purchase_order_status"]


class DashboardActivityItemResponse(BaseModel):
    id: str
    kind: ActivityKind
    occurred_at: datetime
    title: str
    subtitle: str
    quantity: Decimal | None = None

    @field_serializer("quantity")
    def serialize_quantity(self, value: Decimal | None) -> str | None:
        return _serialize_decimal(value)


class DashboardActivityResponse(BaseModel):
    items: list[DashboardActivityItemResponse] = Field(default_factory=list)
