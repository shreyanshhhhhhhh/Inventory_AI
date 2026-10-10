from pydantic import BaseModel, EmailStr, Field, field_validator


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    business_name: str = Field(min_length=1, max_length=200)

    @field_validator("full_name", "business_name")
    @classmethod
    def reject_blank(cls, value: str, info: object) -> str:
        stripped = value.strip()
        field_name = getattr(info, "field_name", "")
        label = "Business name" if field_name == "business_name" else "Name"
        if not stripped:
            raise ValueError(f"{label} is required.")
        return stripped

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, value: str) -> str:
        return value.lower()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, value: str) -> str:
        return value.lower()


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name is required.")
        return stripped

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, value: str | None) -> str | None:
        return value.lower() if value is not None else None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    business_id: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class BusinessResponse(BaseModel):
    id: str
    name: str
    currency_code: str
    onboarding_completed: bool = False


class OwnerOnlyResponse(BaseModel):
    ok: bool
