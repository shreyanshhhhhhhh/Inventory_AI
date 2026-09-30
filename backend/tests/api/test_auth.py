from app.core.security import hash_password
from app.models import User


def _signup(client, *, email: str, business_name: str, password: str = "correct-horse-1"):
    return client.post(
        "/auth/signup",
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
        "/auth/login",
        json={"email": "ada@example.com", "password": "correct-horse-1"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "ada@example.com"
    assert me.json()["business_id"] == body["user"]["business_id"]

    missing = client.get("/auth/me")
    assert missing.status_code == 401
    assert missing.json()["detail"] == "Sign in is required."

    invalid = client.get("/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "Access token is invalid."


def test_wrong_password(client) -> None:
    _signup(client, email="ada@example.com", business_name="North Shop")
    wrong = client.post(
        "/auth/login",
        json={"email": "ada@example.com", "password": "not-the-password"},
    )
    assert wrong.status_code == 401
    assert wrong.json()["detail"] == "Email or password is incorrect."

    missing = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "not-the-password"},
    )
    assert missing.status_code == 401
    assert missing.json()["detail"] == "Email or password is incorrect."


def test_refresh_rotates_and_logout_revokes(client) -> None:
    signup = _signup(client, email="ada@example.com", business_name="North Shop")
    first = signup.json()["refresh_token"]

    refreshed = client.post("/auth/refresh", json={"refresh_token": first})
    assert refreshed.status_code == 200
    second = refreshed.json()["refresh_token"]
    assert second != first
    me = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
    )
    assert me.status_code == 200

    reused = client.post("/auth/refresh", json={"refresh_token": first})
    assert reused.status_code == 401
    assert reused.json()["detail"] == "Refresh token is invalid."

    logout = client.post("/auth/logout", json={"refresh_token": second})
    assert logout.status_code == 204
    after_logout = client.post("/auth/refresh", json={"refresh_token": second})
    assert after_logout.status_code == 401


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
        "/auth/login",
        json={"email": "staff@example.com", "password": "staff-pass-123"},
    )
    assert staff_login.status_code == 200
    staff_token = staff_login.json()["access_token"]

    denied = client.get("/auth/owner-only", headers={"Authorization": f"Bearer {staff_token}"})
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Owner access is required."

    allowed = client.get("/auth/owner-only", headers={"Authorization": f"Bearer {owner_token}"})
    assert allowed.status_code == 200
    assert allowed.json() == {"ok": True}


def test_tenant_scope_uses_token_business(client) -> None:
    shop_a = _signup(client, email="a@example.com", business_name="Shop A")
    shop_b = _signup(client, email="b@example.com", business_name="Shop B")
    token_a = shop_a.json()["access_token"]
    business_a = shop_a.json()["user"]["business_id"]
    business_b = shop_b.json()["user"]["business_id"]

    current = client.get(
        f"/businesses/current?business_id={business_b}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert current.status_code == 200
    assert current.json() == {
        "id": business_a,
        "name": "Shop A",
        "currency_code": "USD",
    }
    assert current.json()["id"] != business_b
