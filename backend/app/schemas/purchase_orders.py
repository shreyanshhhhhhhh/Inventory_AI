from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

TransitionAction = Literal["approve", "send", "receive", "cancel"]


def _serialize_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    normalized = value.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


class PurchaseOrderLineWrite(BaseModel):
    product_id: str
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal | None = Field(default=None, ge=0)


class PurchaseOrderCreateRequest(BaseModel):
    supplier_id: str
    expected_date: date | None = None
    location_id: str | None = None
    notes: str | None = None
    line_items: list[PurchaseOrderLineWrite] = Field(min_length=1)

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class PurchaseOrderUpdateRequest(BaseModel):
    supplier_id: str | None = None
    expected_date: date | None = None
    location_id: str | None = None
    notes: str | None = None
    line_items: list[PurchaseOrderLineWrite] | None = None

    @model_validator(mode="after")
    def require_payload(self) -> "PurchaseOrderUpdateRequest":
        if (
            self.supplier_id is None
            and self.expected_date is None
            and self.location_id is None
            and self.notes is None
            and self.line_items is None
        ):
            raise ValueError("At least one field must be provided.")
        return self


class PurchaseOrderLineResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    quantity: Decimal
    unit_cost: Decimal
    line_total: Decimal

    @field_serializer("quantity", "unit_cost", "line_total")
    def serialize_decimal(self, value: Decimal) -> str:
        return _serialize_decimal(value) or "0"


class PurchaseOrderResponse(BaseModel):
    id: str
    po_number: str
    supplier_id: str
    supplier_name: str
    location_id: str
    status: str
    expected_date: date | None
    notes: str | None
    ordered_at: datetime | None
    total: Decimal
    line_items: list[PurchaseOrderLineResponse]

    @field_serializer("total")
    def serialize_total(self, value: Decimal) -> str:
        return _serialize_decimal(value) or "0"


class PurchaseOrderListResponse(BaseModel):
    items: list[PurchaseOrderResponse]
    total: int
    page: int
    page_size: int


class PurchaseOrderTransitionRequest(BaseModel):
    action: TransitionAction

    @field_validator("action", mode="before")
    @classmethod
    def normalize_action(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value
