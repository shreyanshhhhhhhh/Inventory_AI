import secrets
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models import Business, Location, RefreshToken, User
from app.services.audit import log_action
from app.models.types import new_id, utcnow
from app.repositories.businesses import get_business
from app.repositories.refresh_tokens import get_refresh_token_by_hash
from app.repositories.users import get_user_by_email, get_user_by_id
from app.schemas.auth import BusinessResponse, TokenResponse, UserResponse

DEFAULT_CURRENCY = "USD"


class AuthError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 401,
        *,
        code: str | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.code = code or _auth_error_code(status_code)
        super().__init__(message)


def _auth_error_code(status_code: int) -> str:
    if status_code == 409:
        return "conflict"
    if status_code == 403:
        return "forbidden"
    if status_code == 404:
        return "not_found"
    return "unauthorized"


def signup(
    session: Session,
    *,
    full_name: str,
    email: str,
    password: str,
    business_name: str,
) -> TokenResponse:
    if get_user_by_email(session, email) is not None:
        raise AuthError("An account with this email already exists.", 409)

    business = Business(
        id=new_id(),
        name=business_name,
        currency_code=DEFAULT_CURRENCY,
        onboarding_completed_at=None,
    )
    user = User(
        id=new_id(),
        business_id=business.id,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role="owner",
        is_active=True,
    )
    location = Location(
        id=new_id(),
        business_id=business.id,
        name="Main location",
        is_default=True,
    )
    session.add(business)
    session.add(user)
    session.add(location)
    session.flush()
    log_action(
        session,
        business_id=business.id,
        actor_user_id=user.id,
        action="auth.signup",
        entity_type="business",
        entity_id=business.id,
        before_data=None,
        after_data={
            "business_name": business.name,
            "currency_code": business.currency_code,
            "user_id": user.id,
            "email": user.email,
            "default_location_id": location.id,
            "default_location_name": location.name,
        },
    )
    raw_refresh = _issue_refresh_token(session, user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if "email" in str(exc.orig).lower():
            raise AuthError("An account with this email already exists.", 409) from exc
        raise
    return _token_response(user, raw_refresh)


def login(session: Session, *, email: str, password: str) -> TokenResponse:
    user = get_user_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("Email or password is incorrect.")
    if not user.is_active:
        raise AuthError("This account is deactivated.")
    _require_membership(user)
    raw_refresh = _issue_refresh_token(session, user)
    session.commit()
    return _token_response(user, raw_refresh)


def refresh(session: Session, *, raw_token: str) -> TokenResponse:
    row = _active_refresh_token(session, raw_token)
    user = get_user_by_id(session, row.user_id)
    if user is None or not user.is_active:
        raise AuthError("Refresh token is invalid.")
    _require_membership(user)
    row.revoked_at = utcnow()
    raw_refresh = _issue_refresh_token(session, user)
    session.commit()
    return _token_response(user, raw_refresh)


def logout(session: Session, *, raw_token: str) -> None:
    row = get_refresh_token_by_hash(session, hash_refresh_token(raw_token))
    if row is not None and row.revoked_at is None:
        row.revoked_at = utcnow()
        session.commit()


def current_business(session: Session, *, business_id: str) -> BusinessResponse:
    business = get_business(session, business_id)
    if business is None:
        raise AuthError("Business was not found.", 404)
    return BusinessResponse(
        id=business.id,
        name=business.name,
        currency_code=business.currency_code,
    )


def _require_membership(user: User) -> None:
    if user.business_id is None or user.role is None:
        raise AuthError("This account is not attached to a business.", 403)


def _issue_refresh_token(session: Session, user: User) -> str:
    raw_token = secrets.token_urlsafe(32)
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_token),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
        )
    )
    return raw_token


def _active_refresh_token(session: Session, raw_token: str) -> RefreshToken:
    row = get_refresh_token_by_hash(session, hash_refresh_token(raw_token))
    if row is None or row.revoked_at is not None or row.expires_at <= utcnow():
        raise AuthError("Refresh token is invalid.")
    return row


def _token_response(user: User, raw_refresh: str) -> TokenResponse:
    _require_membership(user)
    assert user.business_id is not None
    assert user.role is not None
    return TokenResponse(
        access_token=create_access_token(
            user_id=user.id,
            business_id=user.business_id,
            role=user.role,
        ),
        refresh_token=raw_refresh,
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            business_id=user.business_id,
        ),
    )
