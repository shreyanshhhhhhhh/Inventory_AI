from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_owner
from app.db import get_db
from app.models import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    OwnerOnlyResponse,
    ProfileUpdateRequest,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import (
    AuthError,
    change_password,
    login,
    logout,
    refresh,
    signup,
    update_profile,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=201)
def signup_route(body: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        return signup(
            db,
            full_name=body.full_name,
            email=body.email,
            password=body.password,
            business_name=body.business_name,
        )
    except AuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.message, "code": exc.code},
        ) from exc


@router.post("/login", response_model=TokenResponse)
def login_route(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        return login(db, email=body.email, password=body.password)
    except AuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.message, "code": exc.code},
        ) from exc


@router.post("/refresh", response_model=TokenResponse)
def refresh_route(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        return refresh(db, raw_token=body.refresh_token)
    except AuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.message, "code": exc.code},
        ) from exc


@router.post("/logout", status_code=204)
def logout_route(body: LogoutRequest, db: Session = Depends(get_db)) -> Response:
    logout(db, raw_token=body.refresh_token)
    return Response(status_code=204)


@router.get("/me", response_model=UserResponse)
def me_route(user: User = Depends(get_current_user)) -> UserResponse:
    if user.business_id is None or user.role is None:
        raise HTTPException(status_code=403, detail="This account is not attached to a business.")
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        business_id=user.business_id,
    )


@router.patch("/me", response_model=UserResponse)
def update_me_route(
    body: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    try:
        return update_profile(db, user_id=user.id, full_name=body.full_name, email=body.email)
    except AuthError as exc:
        raise _auth_http_error(exc) from exc


@router.post("/change-password", response_model=TokenResponse)
def change_password_route(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenResponse:
    try:
        return change_password(
            db,
            user_id=user.id,
            current_password=body.current_password,
            new_password=body.new_password,
        )
    except AuthError as exc:
        raise _auth_http_error(exc) from exc


def _auth_http_error(exc: AuthError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"detail": exc.message, "code": exc.code},
    )


@router.get("/owner-only", response_model=OwnerOnlyResponse)
def owner_only_route(_user: User = Depends(require_owner)) -> OwnerOnlyResponse:
    return OwnerOnlyResponse(ok=True)
