from tests.helpers.tenant import auth_headers, signup_tenant


def _create_staff(client, owner_headers, *, email: str) -> None:
    response = client.post(
        "/api/v1/settings/users",
        headers=owner_headers,
        json={
            "full_name": "Sam Staff",
            "email": email,
            "temporary_password": "temp-pass-123",
        },
    )
    assert response.status_code == 201, response.text


def _staff_login(client, *, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "temp-pass-123"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_staff_blocked_from_settings(client, db) -> None:
    owner = signup_tenant(
        client,
        email="settings-api-owner@example.com",
        business_name="API Settings Shop",
    )
    owner_headers = auth_headers(owner.access_token)
    staff_email = "settings-api-staff@example.com"
    _create_staff(client, owner_headers, email=staff_email)
    staff_token = _staff_login(client, email=staff_email)
    staff_headers = auth_headers(staff_token)

    blocked = client.get("/api/v1/settings/users", headers=staff_headers)
    assert blocked.status_code == 403

    owner_list = client.get("/api/v1/settings/users", headers=owner_headers)
    assert owner_list.status_code == 200
    assert len(owner_list.json()) == 2
