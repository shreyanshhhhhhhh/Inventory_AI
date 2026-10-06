from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_owner
from app.db import get_db
from app.models import User
from app.schemas.auth import BusinessResponse
from app.schemas.settings import (
    AutonomyRulesResponse,
    AutonomyRulesUpdateRequest,
    BusinessUpdateRequest,
    CreateStaffRequest,
    LocationSettingsResponse,
    LocationUpdateRequest,
    LocationWriteRequest,
    TeamUserResponse,
    UpdateUserRoleRequest,
)
from app.services import settings as settings_service
from app.services import team as team_service
from app.services.settings import SettingsError

router = APIRouter(prefix="/settings", tags=["settings"])


def _require_business(user: User) -> str:
    if user.business_id is None:
        raise HTTPException(status_code=403, detail="This account is not attached to a business.")
    return user.business_id


def _handle_settings_error(exc: SettingsError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"detail": exc.message, "code": exc.code},
    )


@router.patch("/business", response_model=BusinessResponse)
def update_business_route(
    body: BusinessUpdateRequest,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> BusinessResponse:
    business_id = _require_business(user)
    if body.name is None and body.currency_code is None:
        raise HTTPException(
            status_code=400,
            detail={"detail": "Provide at least one field to update.", "code": "bad_request"},
        )
    try:
        payload = settings_service.update_business_profile(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            name=body.name,
            currency_code=body.currency_code,
        )
    except SettingsError as exc:
        raise _handle_settings_error(exc) from exc
    return BusinessResponse.model_validate(payload)


@router.get("/locations", response_model=list[LocationSettingsResponse])
def list_locations_route(
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> list[LocationSettingsResponse]:
    business_id = _require_business(user)
    rows = settings_service.list_locations(db, business_id=business_id)
    return [LocationSettingsResponse.model_validate(row) for row in rows]


@router.post("/locations", response_model=LocationSettingsResponse, status_code=201)
def create_location_route(
    body: LocationWriteRequest,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> LocationSettingsResponse:
    business_id = _require_business(user)
    try:
        row = settings_service.create_location(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            name=body.name,
            address=body.address,
            is_default=body.is_default,
        )
    except SettingsError as exc:
        raise _handle_settings_error(exc) from exc
    return LocationSettingsResponse.model_validate(row)


@router.patch("/locations/{location_id}", response_model=LocationSettingsResponse)
def update_location_route(
    location_id: str,
    body: LocationUpdateRequest,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> LocationSettingsResponse:
    business_id = _require_business(user)
    try:
        row = settings_service.update_location(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            location_id=location_id,
            name=body.name,
            address=body.address,
            is_default=body.is_default,
        )
    except SettingsError as exc:
        raise _handle_settings_error(exc) from exc
    return LocationSettingsResponse.model_validate(row)


@router.delete("/locations/{location_id}", status_code=204)
def archive_location_route(
    location_id: str,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> None:
    business_id = _require_business(user)
    try:
        settings_service.archive_location(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            location_id=location_id,
        )
    except SettingsError as exc:
        raise _handle_settings_error(exc) from exc


@router.get("/users", response_model=list[TeamUserResponse])
def list_users_route(
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> list[TeamUserResponse]:
    business_id = _require_business(user)
    rows = team_service.list_users(db, business_id=business_id)
    return [TeamUserResponse.model_validate(row) for row in rows]


@router.post("/users", response_model=TeamUserResponse, status_code=201)
def create_staff_route(
    body: CreateStaffRequest,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> TeamUserResponse:
    business_id = _require_business(user)
    try:
        row = team_service.create_staff_user(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            full_name=body.full_name,
            email=body.email,
            temporary_password=body.temporary_password,
        )
    except SettingsError as exc:
        raise _handle_settings_error(exc) from exc
    return TeamUserResponse.model_validate(row)


@router.patch("/users/{user_id}/role", response_model=TeamUserResponse)
def update_user_role_route(
    user_id: str,
    body: UpdateUserRoleRequest,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> TeamUserResponse:
    business_id = _require_business(user)
    try:
        row = team_service.update_user_role(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            user_id=user_id,
            role=body.role,
        )
    except SettingsError as exc:
        raise _handle_settings_error(exc) from exc
    return TeamUserResponse.model_validate(row)


@router.get("/autonomy-rules", response_model=AutonomyRulesResponse)
def get_autonomy_rules_route(
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AutonomyRulesResponse:
    business_id = _require_business(user)
    payload = settings_service.get_autonomy_rules(db, business_id=business_id)
    return AutonomyRulesResponse.model_validate(payload)


@router.patch("/autonomy-rules", response_model=AutonomyRulesResponse)
def update_autonomy_rules_route(
    body: AutonomyRulesUpdateRequest,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AutonomyRulesResponse:
    business_id = _require_business(user)
    try:
        payload = settings_service.update_autonomy_rules(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            auto_approve_below_amount=body.auto_approve_below_amount,
            exception_scan_enabled=body.exception_scan_enabled,
            exception_scan_hour_utc=body.exception_scan_hour_utc,
        )
    except SettingsError as exc:
        raise _handle_settings_error(exc) from exc
    return AutonomyRulesResponse.model_validate(payload)
