from sqlalchemy import select

from app.core.security import hash_password
from app.models import Location, User
from tests.helpers.tenant import auth_headers, signup_tenant


def _signup(client, *, email: str, business_name: str, password: str = "correct-horse-1"):
    return client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Ada Owner",
            "email": email,
            "password": password,
            "business_name": business_name,
        },
    )


def test_signup_login_and_me(client) -> None:
    signup = _signup(client, email="Ada@Example.com", business_name="North Shop")
    assert signup.status_code == 201
    body = signup.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "owner"
    assert body["user"]["email"] == "ada@example.com"
    assert body["user"]["business_id"]

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "correct-horse-1"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert me.status_code == 200
    assert me.json()["email"] == "ada@example.com"
    assert me.json()["business_id"] == body["user"]["business_id"]

    missing = client.get("/api/v1/auth/me")
    assert missing.status_code == 401
    assert missing.json()["detail"] == "Sign in is required."
    assert missing.json()["code"] == "unauthorized"

    invalid = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "Access token is invalid."


def test_signup_creates_default_location(client, db) -> None:
    tenant = signup_tenant(client, email="owner@example.com", business_name="Harbor Market")
    location = db.scalar(
        select(Location).where(
            Location.business_id == tenant.business_id,
            Location.is_default.is_(True),
        )
    )
    assert location is not None
    assert location.name == "Main location"


def test_wrong_password(client) -> None:
    _signup(client, email="ada@example.com", business_name="North Shop")
    wrong = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "not-the-password"},
    )
    assert wrong.status_code == 401
    assert wrong.json()["detail"] == "Email or password is incorrect."

    missing = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "not-the-password"},
    )
    assert missing.status_code == 401
    assert missing.json()["detail"] == "Email or password is incorrect."


def test_refresh_rotates_and_logout_revokes(client) -> None:
    signup = _signup(client, email="ada@example.com", business_name="North Shop")
    first = signup.json()["refresh_token"]

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert refreshed.status_code == 200
    second = refreshed.json()["refresh_token"]
    assert second != first
    me = client.get(
        "/api/v1/auth/me",
        headers=auth_headers(refreshed.json()["access_token"]),
    )
    assert me.status_code == 200

    logout = client.post("/api/v1/auth/logout", json={"refresh_token": second})
    assert logout.status_code == 204
    after_logout = client.post("/api/v1/auth/refresh", json={"refresh_token": second})
    assert after_logout.status_code == 401


def test_reused_refresh_token_revokes_the_whole_session(client) -> None:
    signup = _signup(client, email="ada@example.com", business_name="North Shop")
    first = signup.json()["refresh_token"]
    second = client.post("/api/v1/auth/refresh", json={"refresh_token": first}).json()["refresh_token"]

    reused = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert reused.status_code == 401
    assert reused.json()["detail"] == "Refresh token is invalid."

    stolen_chain = client.post("/api/v1/auth/refresh", json={"refresh_token": second})
    assert stolen_chain.status_code == 401


def test_change_password_and_profile(client) -> None:
    tenant = signup_tenant(client, email="ada@example.com", business_name="North Shop")
    headers = auth_headers(tenant.access_token)

    wrong = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "nope-nope-1", "new_password": "brand-new-pass-1"},
        headers=headers,
    )
    assert wrong.status_code == 400
    assert wrong.json()["code"] == "invalid_password"

    changed = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "correct-horse-1", "new_password": "brand-new-pass-1"},
        headers=headers,
    )
    assert changed.status_code == 200
    old_refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": tenant.refresh_token})
    assert old_refresh.status_code == 401
    relogin = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "brand-new-pass-1"},
    )
    assert relogin.status_code == 200

    profile = client.patch(
        "/api/v1/auth/me",
        json={"full_name": "Ada Lovelace", "email": "ADA.L@example.com"},
        headers=headers,
    )
    assert profile.status_code == 200
    assert profile.json()["full_name"] == "Ada Lovelace"
    assert profile.json()["email"] == "ada.l@example.com"

    signup_tenant(client, email="taken@example.com", business_name="Other")
    taken = client.patch("/api/v1/auth/me", json={"email": "taken@example.com"}, headers=headers)
    assert taken.status_code == 409


def test_error_shape_for_validation_and_unknown_routes(client) -> None:
    invalid = client.post("/api/v1/auth/login", json={"email": "not-an-email"})
    assert invalid.status_code == 422
    body = invalid.json()
    assert body["code"] == "validation_error"
    assert isinstance(body["detail"], str)

    missing = client.get("/api/v1/does-not-exist")
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_found"


def test_staff_cannot_pass_owner_only(client, db) -> None:
    signup = _signup(client, email="ada@example.com", business_name="North Shop")
    owner_token = signup.json()["access_token"]
    business_id = signup.json()["user"]["business_id"]
    db.add(
        User(
            business_id=business_id,
            email="staff@example.com",
            password_hash=hash_password("staff-pass-123"),
            full_name="Sam Staff",
            role="staff",
            is_active=True,
        )
    )
    db.commit()

    staff_login = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@example.com", "password": "staff-pass-123"},
    )
    assert staff_login.status_code == 200
    staff_token = staff_login.json()["access_token"]

    denied = client.get(
        "/api/v1/auth/owner-only",
        headers=auth_headers(staff_token),
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Owner access is required."

    allowed = client.get(
        "/api/v1/auth/owner-only",
        headers=auth_headers(owner_token),
    )
    assert allowed.status_code == 200
    assert allowed.json() == {"ok": True}


def test_tenant_scope_uses_token_business(client) -> None:
    shop_a = signup_tenant(client, email="a@example.com", business_name="Shop A")
    shop_b = signup_tenant(client, email="b@example.com", business_name="Shop B")

    current = client.get(
        f"/api/v1/businesses/current?business_id={shop_b.business_id}",
        headers=auth_headers(shop_a.access_token),
    )
    assert current.status_code == 200
    assert current.json() == {
        "id": shop_a.business_id,
        "name": "Shop A",
        "currency_code": "USD",
        "onboarding_completed": False,
    }
    assert current.json()["id"] != shop_b.business_id
