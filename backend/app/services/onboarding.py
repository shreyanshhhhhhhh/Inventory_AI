from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Business, Location, Product, Supplier
from app.models.types import utcnow
from app.services.audit import log_action


class OnboardingError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, code: str = "bad_request") -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


def _count_active(session: Session, model: type[Location] | type[Product] | type[Supplier], business_id: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(model)
            .where(model.business_id == business_id, model.archived_at.is_(None))
        )
        or 0
    )


def get_onboarding_status(session: Session, *, business_id: str) -> dict[str, object]:
    business = session.get(Business, business_id)
    if business is None:
        raise OnboardingError("Business not found.", status_code=404, code="not_found")
    location_count = _count_active(session, Location, business_id)
    product_count = _count_active(session, Product, business_id)
    supplier_count = _count_active(session, Supplier, business_id)
    return {
        "completed": business.onboarding_completed_at is not None,
        "completed_at": business.onboarding_completed_at,
        "business_name": business.name,
        "currency_code": business.currency_code,
        "location_count": location_count,
        "product_count": product_count,
        "supplier_count": supplier_count,
        "can_complete": location_count > 0 and product_count > 0 and supplier_count > 0,
    }


def is_onboarding_complete(session: Session, *, business_id: str) -> bool:
    business = session.get(Business, business_id)
    return business is not None and business.onboarding_completed_at is not None


def complete_onboarding(session: Session, *, business_id: str, actor_user_id: str) -> dict[str, object]:
    status = get_onboarding_status(session, business_id=business_id)
    if status["completed"]:
        return status
    missing: list[str] = []
    if not status["location_count"]:
        missing.append("a location")
    if not status["product_count"]:
        missing.append("at least one product (CSV import or demo data)")
    if not status["supplier_count"]:
        missing.append("a supplier")
    if missing:
        raise OnboardingError(
            f"Finish onboarding first: add {', '.join(missing)}.",
            status_code=409,
            code="onboarding_incomplete",
        )

    business = session.get(Business, business_id)
    assert business is not None
    business.onboarding_completed_at = utcnow()
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="onboarding.complete",
        entity_type="business",
        entity_id=business_id,
        before_data={"onboarding_completed_at": None},
        after_data={
            "onboarding_completed_at": business.onboarding_completed_at.isoformat(),
            "currency_code": business.currency_code,
        },
    )
    session.commit()
    return get_onboarding_status(session, business_id=business_id)
