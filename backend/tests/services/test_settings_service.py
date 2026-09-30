from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.security import hash_password
from app.models import AuditLog, AutonomyRules, User
from app.models.types import new_id
from app.repositories import inventory as inventory_repo
from app.services.auth import signup
from app.services.settings import (
    SettingsError,
    archive_location,
    create_location,
    get_autonomy_rules,
    update_autonomy_rules,
    update_business_profile,
    update_location,
)
from app.services.team import create_staff_user, list_users, update_user_role


def _owner(db, *, email: str, business_name: str):
    return signup(
        db,
        full_name="Ada Owner",
        email=email,
        password="correct-horse-1",
        business_name=business_name,
    )


def _staff_user(db, *, business_id: str, email: str) -> User:
    user = User(
        id=new_id(),
        business_id=business_id,
        email=email,
        password_hash=hash_password("staff-pass-123"),
        full_name="Staff User",
        role="staff",
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def test_update_business_and_autonomy_rules(db) -> None:
    owner = _owner(db, email="settings-owner@example.com", business_name="Settings Shop")
    business_id = owner.user.business_id

    updated = update_business_profile(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        name="Updated Shop",
        currency_code="EUR",
    )
    assert updated["name"] == "Updated Shop"
    assert updated["currency_code"] == "EUR"

    rules = get_autonomy_rules(db, business_id=business_id)
    assert rules["auto_approve_below_amount"] is None

    updated_rules = update_autonomy_rules(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        auto_approve_below_amount=Decimal("250.00"),
    )
    assert updated_rules["auto_approve_below_amount"] == Decimal("250.00")
    assert db.scalar(select(AutonomyRules).where(AutonomyRules.business_id == business_id)) is not None

    audit_count = db.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.business_id == business_id,
            AuditLog.action.in_(("business.update", "autonomy_rules.update")),
        )
    )
    assert int(audit_count or 0) >= 2


def test_location_crud(db) -> None:
    owner = _owner(db, email="settings-loc@example.com", business_name="Loc Shop")
    business_id = owner.user.business_id
    default_id = inventory_repo.list_locations(db, business_id)[0].id

    created = create_location(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        name="Back room",
        address="Rear dock",
        is_default=False,
    )
    assert created["name"] == "Back room"

    updated = update_location(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        location_id=created["id"],
        name="Backroom",
        address=None,
        is_default=True,
    )
    assert updated["is_default"] is True
    default = inventory_repo.get_location(db, business_id, default_id)
    assert default is not None
    assert default.is_default is False


def test_cannot_archive_last_or_default_location(db) -> None:
    owner = _owner(db, email="settings-archive@example.com", business_name="Archive Shop")
    business_id = owner.user.business_id
    location_id = inventory_repo.list_locations(db, business_id)[0].id

    with pytest.raises(SettingsError) as exc:
        archive_location(
            db,
            business_id=business_id,
            actor_user_id=owner.user.id,
            location_id=location_id,
        )
    assert exc.value.code == "conflict"


def test_create_staff_and_last_owner_protection(db) -> None:
    owner = _owner(db, email="settings-team@example.com", business_name="Team Shop")
    business_id = owner.user.business_id

    staff = create_staff_user(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        full_name="Sam Staff",
        email="sam-staff@example.com",
        temporary_password="temp-pass-123",
    )
    assert staff["role"] == "staff"
    assert len(list_users(db, business_id=business_id)) == 2

    with pytest.raises(SettingsError) as exc:
        update_user_role(
            db,
            business_id=business_id,
            actor_user_id=owner.user.id,
            user_id=owner.user.id,
            role="staff",
        )
    assert exc.value.code == "last_owner"


def test_tenant_isolation_for_team(db) -> None:
    owner_a = _owner(db, email="settings-a@example.com", business_name="Settings A")
    owner_b = _owner(db, email="settings-b@example.com", business_name="Settings B")
    _staff_user(db, business_id=owner_a.user.business_id, email="staff-a@example.com")

    users_a = list_users(db, business_id=owner_a.user.business_id)
    users_b = list_users(db, business_id=owner_b.user.business_id)
    assert len(users_a) == 2
    assert len(users_b) == 1
    assert {user["email"] for user in users_a} == {
        owner_a.user.email,
        "staff-a@example.com",
    }
    assert users_b[0]["email"] == owner_b.user.email
