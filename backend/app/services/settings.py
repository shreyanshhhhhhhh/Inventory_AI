from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AutonomyRules, Business, Location
from app.models.types import new_id, utcnow
from app.repositories import inventory as inventory_repo
from app.repositories.businesses import get_business
from app.services.audit import log_action


class SettingsError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, code: str = "bad_request") -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


def _business_payload(business: Business) -> dict[str, object]:
    return {
        "id": business.id,
        "name": business.name,
        "currency_code": business.currency_code,
    }


def _location_payload(location: Location) -> dict[str, object]:
    return {
        "id": location.id,
        "name": location.name,
        "address": location.address,
        "is_default": location.is_default,
    }


def _autonomy_rules_data(rules: AutonomyRules) -> dict[str, object]:
    return {
        "auto_approve_below_amount": rules.auto_approve_below_amount,
        "exception_scan_enabled": rules.exception_scan_enabled,
        "exception_scan_hour_utc": rules.exception_scan_hour_utc,
        "exception_scan_last_run_on": rules.exception_scan_last_run_on,
    }


def _autonomy_audit_data(rules: AutonomyRules) -> dict[str, object]:
    amount = rules.auto_approve_below_amount
    last_run = rules.exception_scan_last_run_on
    return {
        "auto_approve_below_amount": str(amount) if amount is not None else None,
        "exception_scan_enabled": rules.exception_scan_enabled,
        "exception_scan_hour_utc": rules.exception_scan_hour_utc,
        "exception_scan_last_run_on": last_run.isoformat() if last_run is not None else None,
    }


def update_business_profile(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    name: str | None,
    currency_code: str | None,
) -> dict[str, object]:
    business = get_business(session, business_id)
    if business is None:
        raise SettingsError("Business not found.", status_code=404, code="not_found")

    before = _business_payload(business)
    if name is not None:
        business.name = name
    if currency_code is not None:
        business.currency_code = currency_code
    session.flush()

    after = _business_payload(business)
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="business.update",
        entity_type="business",
        entity_id=business.id,
        before_data=before,
        after_data=after,
    )
    session.commit()
    session.refresh(business)
    return after


def list_locations(session: Session, *, business_id: str) -> list[dict[str, object]]:
    return [
        _location_payload(location)
        for location in inventory_repo.list_locations(session, business_id)
    ]


def create_location(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    name: str,
    address: str | None,
    is_default: bool,
) -> dict[str, object]:
    existing = inventory_repo.list_locations(session, business_id)
    if is_default:
        for location in existing:
            location.is_default = False

    location = Location(
        id=new_id(),
        business_id=business_id,
        name=name,
        address=address,
        is_default=is_default or len(existing) == 0,
    )
    session.add(location)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise SettingsError(
            "A location with this name already exists.",
            status_code=409,
            code="conflict",
        ) from exc

    payload = _location_payload(location)
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="location.create",
        entity_type="location",
        entity_id=location.id,
        before_data=None,
        after_data=payload,
    )
    session.commit()
    session.refresh(location)
    return payload


def update_location(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    location_id: str,
    name: str | None,
    address: str | None,
    is_default: bool | None,
) -> dict[str, object]:
    location = inventory_repo.get_location(session, business_id, location_id)
    if location is None:
        raise SettingsError("Location not found.", status_code=404, code="not_found")

    before = _location_payload(location)
    if name is not None:
        location.name = name
    if address is not None:
        location.address = address
    if is_default is True:
        for other in inventory_repo.list_locations(session, business_id):
            other.is_default = other.id == location.id
    elif is_default is False and location.is_default:
        active = inventory_repo.list_locations(session, business_id)
        if len(active) <= 1:
            raise SettingsError(
                "The business must keep one default location.",
                status_code=409,
                code="conflict",
            )
        location.is_default = False
        replacement = next(item for item in active if item.id != location.id)
        replacement.is_default = True

    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise SettingsError(
            "A location with this name already exists.",
            status_code=409,
            code="conflict",
        ) from exc

    after = _location_payload(location)
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="location.update",
        entity_type="location",
        entity_id=location.id,
        before_data=before,
        after_data=after,
    )
    session.commit()
    session.refresh(location)
    return after


def archive_location(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    location_id: str,
) -> None:
    location = inventory_repo.get_location(session, business_id, location_id)
    if location is None:
        raise SettingsError("Location not found.", status_code=404, code="not_found")

    active = inventory_repo.list_locations(session, business_id)
    if len(active) <= 1:
        raise SettingsError(
            "The business must keep at least one active location.",
            status_code=409,
            code="conflict",
        )
    if location.is_default:
        raise SettingsError(
            "Assign a different default location before archiving this one.",
            status_code=409,
            code="conflict",
        )

    before = _location_payload(location)
    location.archived_at = utcnow()
    session.flush()

    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="location.archive",
        entity_type="location",
        entity_id=location.id,
        before_data=before,
        after_data={"id": location.id, "archived_at": location.archived_at.isoformat()},
    )
    session.commit()


def _get_or_create_autonomy_rules(session: Session, business_id: str) -> AutonomyRules:
    rules = session.scalar(
        select(AutonomyRules).where(AutonomyRules.business_id == business_id)
    )
    if rules is not None:
        return rules
    rules = AutonomyRules(
        id=new_id(),
        business_id=business_id,
        auto_approve_below_amount=None,
        exception_scan_enabled=True,
        exception_scan_hour_utc=2,
        exception_scan_last_run_on=None,
    )
    session.add(rules)
    session.flush()
    return rules


def get_autonomy_rules(session: Session, *, business_id: str) -> dict[str, object]:
    rules = _get_or_create_autonomy_rules(session, business_id)
    return _autonomy_rules_data(rules)


def update_autonomy_rules(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    auto_approve_below_amount: Decimal | None,
    exception_scan_enabled: bool | None = None,
    exception_scan_hour_utc: int | None = None,
) -> dict[str, object]:
    if exception_scan_hour_utc is not None and (
        exception_scan_hour_utc < 0 or exception_scan_hour_utc > 23
    ):
        raise SettingsError("Scan hour must be between 0 and 23 UTC.")
    rules = _get_or_create_autonomy_rules(session, business_id)
    before = _autonomy_audit_data(rules)
    rules.auto_approve_below_amount = auto_approve_below_amount
    if exception_scan_enabled is not None:
        rules.exception_scan_enabled = exception_scan_enabled
    if exception_scan_hour_utc is not None:
        rules.exception_scan_hour_utc = exception_scan_hour_utc
    session.flush()
    after = _autonomy_audit_data(rules)
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="autonomy_rules.update",
        entity_type="autonomy_rules",
        entity_id=rules.id,
        before_data=before,
        after_data=after,
    )
    session.commit()
    session.refresh(rules)
    return _autonomy_rules_data(rules)


def mark_exception_scan_run(
    session: Session,
    *,
    business_id: str,
    ran_on: date,
) -> None:
    rules = _get_or_create_autonomy_rules(session, business_id)
    rules.exception_scan_last_run_on = ran_on
    session.flush()
