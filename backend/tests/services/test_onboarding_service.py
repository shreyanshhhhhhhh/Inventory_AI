import pytest
from sqlalchemy import func, select

from app.models import AuditLog
from app.services.catalog import create_supplier
from app.services.demo_seed import load_demo_data
from app.services.onboarding import (
    OnboardingError,
    complete_onboarding,
    get_onboarding_status,
    is_onboarding_complete,
)
from tests.helpers.tenant import signup_service_tenant


def test_new_business_starts_incomplete(db) -> None:
    owner = signup_service_tenant(db, email="onboard-new@example.com", business_name="New Shop")
    status = get_onboarding_status(db, business_id=owner.user.business_id)
    assert status["completed"] is False
    assert status["location_count"] == 1
    assert status["product_count"] == 0
    assert status["can_complete"] is False


def test_complete_requires_catalog_and_supplier(db) -> None:
    owner = signup_service_tenant(db, email="onboard-req@example.com", business_name="Req Shop")
    business_id = owner.user.business_id

    create_supplier(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        name="Only Supplier",
        email=None,
        phone=None,
        lead_time_days=1,
    )
    with pytest.raises(OnboardingError) as exc:
        complete_onboarding(db, business_id=business_id, actor_user_id=owner.user.id)
    assert exc.value.code == "onboarding_incomplete"
    assert "product" in exc.value.message
    assert is_onboarding_complete(db, business_id=business_id) is False


def test_demo_data_then_complete(db) -> None:
    owner = signup_service_tenant(db, email="onboard-demo@example.com", business_name="Demo Shop")
    business_id = owner.user.business_id

    load_demo_data(db, business_id=business_id, actor_user_id=owner.user.id)
    assert is_onboarding_complete(db, business_id=business_id) is False

    status = complete_onboarding(db, business_id=business_id, actor_user_id=owner.user.id)
    assert status["completed"] is True
    assert is_onboarding_complete(db, business_id=business_id) is True
    audit_count = db.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.business_id == business_id, AuditLog.action == "onboarding.complete")
    )
    assert audit_count == 1


def test_onboarding_status_is_tenant_scoped(db) -> None:
    owner_a = signup_service_tenant(db, email="onboard-a@example.com", business_name="A Shop")
    owner_b = signup_service_tenant(db, email="onboard-b@example.com", business_name="B Shop")
    load_demo_data(db, business_id=owner_a.user.business_id, actor_user_id=owner_a.user.id)
    complete_onboarding(db, business_id=owner_a.user.business_id, actor_user_id=owner_a.user.id)

    status_b = get_onboarding_status(db, business_id=owner_b.user.business_id)
    assert status_b["completed"] is False
    assert status_b["product_count"] == 0
