from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_serializer, field_validator

from app.schemas.inventory import _serialize_decimal


class BusinessUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Business name is required.")
        return stripped

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("Currency must be a 3-letter ISO code.")
        return normalized


class LocationWriteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str | None = None
    is_default: bool = False

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Location name is required.")
        return stripped


class LocationUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    address: str | None = None
    is_default: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Location name is required.")
        return stripped


class LocationSettingsResponse(BaseModel):
    id: str
    name: str
    address: str | None
    is_default: bool


class TeamUserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool


class CreateStaffRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    temporary_password: str = Field(min_length=8, max_length=200)

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name is required.")
        return stripped

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, value: str) -> str:
        return value.lower()


class UpdateUserRoleRequest(BaseModel):
    role: Literal["owner", "staff"]


class AutonomyRulesResponse(BaseModel):
    auto_approve_below_amount: Decimal | None
    exception_scan_enabled: bool = True
    exception_scan_hour_utc: int = 2
    exception_scan_last_run_on: date | None = None
    chase_followup_days: int = 3

    @field_serializer("auto_approve_below_amount")
    def serialize_amount(self, value: Decimal | None) -> str | None:
        return _serialize_decimal(value)


class AutonomyRulesUpdateRequest(BaseModel):
    auto_approve_below_amount: Decimal | None = None
    exception_scan_enabled: bool | None = None
    exception_scan_hour_utc: int | None = Field(default=None, ge=0, le=23)
    chase_followup_days: int | None = Field(default=None, ge=1, le=90)
