from tests.helpers.tenant import auth_headers, signup_tenant


def test_owner_can_run_exception_scan_job(client) -> None:
    owner = signup_tenant(client, email="job-owner@example.com", business_name="Job Shop")
    response = client.post(
        "/api/v1/jobs/exception-scan",
        headers=auth_headers(owner.access_token),
        json={"force": True},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ran"] == 1
    assert body["businesses"][0]["business_id"] == owner.business_id


def test_staff_cannot_run_exception_scan_job(client) -> None:
    owner = signup_tenant(client, email="job-staff-owner@example.com", business_name="Staff Job")
    staff = client.post(
        "/api/v1/settings/users",
        headers=auth_headers(owner.access_token),
        json={
            "full_name": "Sam Staff",
            "email": "job-staff@example.com",
            "temporary_password": "temp-pass-123",
        },
    )
    assert staff.status_code == 201, staff.text
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "job-staff@example.com", "password": "temp-pass-123"},
    )
    token = login.json()["access_token"]
    blocked = client.post(
        "/api/v1/jobs/exception-scan",
        headers=auth_headers(token),
        json={"force": True},
    )
    assert blocked.status_code == 403


def test_job_secret_can_run_scan(client, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "job_secret", "test-job-secret")
    owner = signup_tenant(client, email="job-secret@example.com", business_name="Secret Job")
    response = client.post(
        "/api/v1/jobs/exception-scan",
        headers={"X-Job-Secret": "test-job-secret"},
        json={"business_id": owner.business_id, "force": True},
    )
    assert response.status_code == 200, response.text
    assert response.json()["ran"] == 1
