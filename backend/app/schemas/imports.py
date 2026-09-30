from pydantic import BaseModel, Field


class ImportRowError(BaseModel):
    row: int
    message: str


class ImportResultResponse(BaseModel):
    imported_count: int
    skipped_count: int
    error_count: int
    errors: list[ImportRowError]
    success: bool


class DemoSeedResponse(BaseModel):
    products_created: int
    suppliers_created: int
    categories_created: int
    stock_movements_created: int
    sale_movements_created: int
    purchase_orders_created: int
    message: str
