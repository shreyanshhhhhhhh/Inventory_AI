from datetime import datetime

from pydantic import BaseModel


class OnboardingStatusResponse(BaseModel):
    completed: bool
    completed_at: datetime | None
    business_name: str
    currency_code: str
    location_count: int
    product_count: int
    supplier_count: int
    can_complete: bool
