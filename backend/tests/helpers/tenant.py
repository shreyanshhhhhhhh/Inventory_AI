from dataclasses import dataclass

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.repositories.businesses import get_business


@dataclass(frozen=True)
class TenantFixture:
    email: str
    business_name: str
    access_token: str
    refresh_token: str
    business_id: str
    user_id: str


def signup_tenant(
    client: TestClient,
    *,
    email: str,
    business_name: str,
    password: str = "correct-horse-1",
    full_name: str = "Test Owner",
) -> TenantFixture:
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": full_name,
            "email": email,
            "password": password,
            "business_name": business_name,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return TenantFixture(
        email=body["user"]["email"],
        business_name=business_name,
        access_token=body["access_token"],
        refresh_token=body["refresh_token"],
        business_id=body["user"]["business_id"],
        user_id=body["user"]["id"],
    )


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def assert_tenant_cannot_see_other_business(
    db: Session,
    *,
    tenant: TenantFixture,
    other_business_id: str,
) -> None:
    business = get_business(db, other_business_id)
    assert business is not None
    visible = get_business(db, tenant.business_id)
    assert visible is not None
    assert visible.id == tenant.business_id
    assert visible.id != other_business_id
