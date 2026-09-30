from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer, field_validator


def _serialize_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


class CategoryResponse(BaseModel):
    id: str
    name: str


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name is required.")
        return stripped


class CategoryUpdateRequest(CategoryCreateRequest):
    pass


class SupplierResponse(BaseModel):
    id: str
    name: str
    email: str | None
    phone: str | None
    lead_time_days: int
    is_active: bool


class SupplierCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    lead_time_days: int = Field(default=0, ge=0)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name is required.")
        return stripped


class SupplierUpdateRequest(SupplierCreateRequest):
    pass


class ProductResponse(BaseModel):
    id: str
    sku: str
    name: str
    category_id: str | None
    category_name: str | None = None
    unit: str
    cost: Decimal | None
    price: Decimal | None
    reorder_point: Decimal | None
    safety_stock: Decimal | None
    preferred_supplier_id: str | None = None
    preferred_supplier_name: str | None = None
    is_active: bool

    @field_serializer("cost", "price", "reorder_point", "safety_stock")
    def serialize_money(self, value: Decimal | None) -> str | None:
        return _serialize_decimal(value)


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    page_size: int


class ProductCreateRequest(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    category_id: str | None = None
    unit: str = Field(default="each", min_length=1, max_length=32)
    cost: Decimal | None = None
    price: Decimal | None = None
    reorder_point: Decimal | None = None
    safety_stock: Decimal | None = None
    preferred_supplier_id: str | None = None

    @field_validator("sku", "name", "unit")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class ProductUpdateRequest(ProductCreateRequest):
    pass


class ProductSupplierResponse(BaseModel):
    id: str
    product_id: str
    supplier_id: str
    supplier_sku: str | None
    unit_cost: Decimal
    lead_time_days: int
    is_preferred: bool

    @field_serializer("unit_cost")
    def serialize_unit_cost(self, value: Decimal) -> str:
        return _serialize_decimal(value) or "0"


class ProductSupplierCreateRequest(BaseModel):
    supplier_id: str
    unit_cost: Decimal
    lead_time_days: int = Field(ge=0)
    supplier_sku: str | None = Field(default=None, max_length=64)
    is_preferred: bool = False


class ProductSupplierUpdateRequest(BaseModel):
    unit_cost: Decimal
    lead_time_days: int = Field(ge=0)
    supplier_sku: str | None = Field(default=None, max_length=64)
    is_preferred: bool = False
