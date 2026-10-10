from tests.helpers.tenant import auth_headers, signup_tenant


def test_dashboard_requires_onboarding(client) -> None:
    owner = signup_tenant(client, email="gate-owner@example.com", business_name="Gate Shop")
    headers = auth_headers(owner.access_token)

    blocked = client.get("/api/v1/dashboard/summary", headers=headers)
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "onboarding_required"

    business = client.patch(
        "/api/v1/settings/business",
        json={"name": "Gate Shop Ltd", "currency_code": "eur"},
        headers=headers,
    )
    assert business.status_code == 200
    assert business.json()["currency_code"] == "EUR"

    early = client.post("/api/v1/onboarding/complete", headers=headers)
    assert early.status_code == 409
    assert early.json()["code"] == "onboarding_incomplete"

    assert client.post("/api/v1/onboarding/load-demo-data", headers=headers).status_code == 200
    done = client.post("/api/v1/onboarding/complete", headers=headers)
    assert done.status_code == 200
    assert done.json()["completed"] is True

    assert client.get("/api/v1/dashboard/summary", headers=headers).status_code == 200
    current = client.get("/api/v1/businesses/current", headers=headers).json()
    assert current["onboarding_completed"] is True

    locked = client.patch(
        "/api/v1/settings/business", json={"currency_code": "GBP"}, headers=headers
    )
    assert locked.status_code == 409
    assert locked.json()["code"] == "currency_locked"


def test_audit_log_is_owner_only_and_tenant_scoped(client) -> None:
    owner = signup_tenant(client, email="audit-owner@example.com", business_name="Audit Shop")
    other = signup_tenant(client, email="audit-other@example.com", business_name="Other Audit")
    headers = auth_headers(owner.access_token)

    created = client.post(
        "/api/v1/settings/users",
        headers=headers,
        json={
            "full_name": "Sam Staff",
            "email": "audit-staff@example.com",
            "temporary_password": "temp-pass-123",
        },
    )
    assert created.status_code == 201

    log = client.get("/api/v1/audit-log", headers=headers)
    assert log.status_code == 200
    actions = {item["action"] for item in log.json()["items"]}
    assert {"auth.signup", "user.create"} <= actions
    assert all(item["entity_id"] != other.business_id for item in log.json()["items"])

    filtered = client.get("/api/v1/audit-log?action=user.create", headers=headers)
    assert filtered.json()["total"] == 1

    staff_token = client.post(
        "/api/v1/auth/login",
        json={"email": "audit-staff@example.com", "password": "temp-pass-123"},
    ).json()["access_token"]
    assert client.get("/api/v1/audit-log", headers=auth_headers(staff_token)).status_code == 403


def test_deactivated_staff_loses_access(client) -> None:
    owner = signup_tenant(client, email="deact-owner@example.com", business_name="Deact Shop")
    headers = auth_headers(owner.access_token)
    staff = client.post(
        "/api/v1/settings/users",
        headers=headers,
        json={
            "full_name": "Sam Staff",
            "email": "deact-api-staff@example.com",
            "temporary_password": "temp-pass-123",
        },
    ).json()
    staff_token = client.post(
        "/api/v1/auth/login",
        json={"email": "deact-api-staff@example.com", "password": "temp-pass-123"},
    ).json()["access_token"]

    response = client.patch(
        f"/api/v1/settings/users/{staff['id']}/active",
        json={"is_active": False},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert client.get("/api/v1/auth/me", headers=auth_headers(staff_token)).status_code == 401
