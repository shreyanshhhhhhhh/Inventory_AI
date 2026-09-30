from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_owner
from app.db import get_db
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    OwnerOnlyResponse,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import AuthError, login, logout, refresh, signup

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
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/login", response_model=TokenResponse)
def login_route(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        return login(db, email=body.email, password=body.password)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/refresh", response_model=TokenResponse)
def refresh_route(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        return refresh(db, raw_token=body.refresh_token)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


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


@router.get("/owner-only", response_model=OwnerOnlyResponse)
def owner_only_route(_user: User = Depends(require_owner)) -> OwnerOnlyResponse:
    return OwnerOnlyResponse(ok=True)
