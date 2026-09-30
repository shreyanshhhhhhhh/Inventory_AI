from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

MovementTypeInput = Literal["receipt", "sale", "adjustment", "transfer"]
MovementTypeResponse = Literal["receipt", "purchase_receipt", "sale", "adjustment", "transfer"]
StockStatus = Literal["in_stock", "low", "out"]


def _serialize_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    normalized = value.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


class LocationResponse(BaseModel):
    id: str
    name: str
    is_default: bool


class StockLevelResponse(BaseModel):
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


class StockListResponse(BaseModel):
    items: list[StockLevelResponse]
    total: int
    page: int
    page_size: int


class MovementResponse(BaseModel):
    id: str
    occurred_at: datetime
    product_id: str
    product_name: str
    location_id: str
    location_name: str
    movement_type: MovementTypeResponse
    quantity: Decimal
    note: str | None
    reason: str | None
    user_id: str
    user_name: str

    @field_serializer("quantity")
    def serialize_quantity(self, value: Decimal) -> str:
        return _serialize_decimal(value) or "0"


class MovementListResponse(BaseModel):
    items: list[MovementResponse]
    total: int
    page: int
    page_size: int


class MovementCreateRequest(BaseModel):
    product_id: str
    location_id: str
    type: MovementTypeInput
    quantity: Decimal
    note: str | None = None
    destination_location_id: str | None = None

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("note")
    @classmethod
    def strip_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_quantity_and_note(self) -> "MovementCreateRequest":
        if self.type in {"receipt", "sale", "transfer"} and self.quantity <= 0:
            raise ValueError("Quantity must be greater than 0 for this movement type.")
        if self.type == "adjustment" and self.quantity == 0:
            raise ValueError("Adjustment quantity cannot be 0.")
        if self.type == "adjustment" and not self.note:
            raise ValueError("Adjustments require a note.")
        if self.type == "transfer" and not self.destination_location_id:
            raise ValueError("Transfers require a destination location.")
        if self.type == "transfer" and self.destination_location_id == self.location_id:
            raise ValueError("Transfer source and destination must differ.")
        return self
