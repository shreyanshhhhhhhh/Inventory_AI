from uuid import uuid4

from tests.helpers.tenant import auth_headers, signup_tenant


def test_staff_cannot_approve_and_owner_miss_is_not_found(client) -> None:
    owner = signup_tenant(client, email="sug-api-owner@example.com", business_name="Sug API")
    staff = client.post(
        "/api/v1/settings/users",
        headers=auth_headers(owner.access_token),
        json={
            "full_name": "Sam Staff",
            "email": "sug-api-staff@example.com",
            "temporary_password": "temp-pass-123",
        },
    )
    assert staff.status_code == 201, staff.text
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "sug-api-staff@example.com", "password": "temp-pass-123"},
    )
    assert login.status_code == 200, login.text
    blocked = client.post(
        f"/api/v1/suggestions/{uuid4()}/approve",
        headers=auth_headers(login.json()["access_token"]),
    )
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "forbidden"

    missing = client.post(
        f"/api/v1/suggestions/{uuid4()}/approve",
        headers=auth_headers(owner.access_token),
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_found"
