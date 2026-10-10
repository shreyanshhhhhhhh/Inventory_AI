from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.agents.runs import start_agent_run
from app.repositories import inventory as inventory_repo
from app.services.catalog import create_product, create_product_supplier, create_supplier
from app.services.purchase_orders import create_po
from app.services.supplier_messages import create_draft
from tests.helpers.tenant import auth_headers, signup_tenant
from tests.orchestrator.helpers import owner


def test_staff_cannot_send_supplier_email(client, db) -> None:
    signed = owner(db, "api-mail-owner@example.com", "API Mail")
    supplier = create_supplier(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        name="Mill",
        email="mill@example.com",
        phone=None,
        lead_time_days=4,
    )
    product = create_product(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        sku="OATS-1",
        name="Oats",
        category_id=None,
        unit="each",
        cost=Decimal("1.00"),
        price=Decimal("2.00"),
        reorder_point=Decimal("10"),
        safety_stock=Decimal("2"),
        preferred_supplier_id=None,
    )
    create_product_supplier(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        product_id=product.id,
        supplier_id=supplier.id,
        unit_cost=Decimal("1.50"),
        lead_time_days=4,
        is_preferred=True,
    )
    po = create_po(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        supplier_id=supplier.id,
        expected_date=date(2026, 10, 20),
        location_id=inventory_repo.list_locations(db, signed.user.business_id)[0].id,
        notes=None,
        line_items=[{"product_id": product.id, "quantity": Decimal("12"), "unit_cost": Decimal("1.50")}],
    )
    run = start_agent_run(
        db,
        business_id=signed.user.business_id,
        agent_name="supplier_comm",
        actor_user_id=signed.user.id,
    )
    drafted = create_draft(
        db,
        business_id=signed.user.business_id,
        actor_user_id=signed.user.id,
        run_id=run.id,
        supplier_id=supplier.id,
        kind="order",
        po_id=str(po["id"]),
        greeting="",
        ask="",
        closing="",
    )
    db.commit()
    owner_login = client.post(
        "/api/v1/auth/login",
        json={"email": "api-mail-owner@example.com", "password": "correct-horse-1"},
    )
    assert owner_login.status_code == 200, owner_login.text
    staff = client.post(
        "/api/v1/settings/users",
        headers=auth_headers(owner_login.json()["access_token"]),
        json={
            "full_name": "Sam Staff",
            "email": "api-mail-staff@example.com",
            "temporary_password": "temp-pass-123",
        },
    )
    assert staff.status_code == 201, staff.text
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "api-mail-staff@example.com", "password": "temp-pass-123"},
    )
    blocked = client.post(
        f"/api/v1/supplier-messages/{drafted['id']}/send",
        headers=auth_headers(login.json()["access_token"]),
        json={},
    )
    assert blocked.status_code == 403
    banner = client.get(
        "/api/v1/supplier-messages/sender-status",
        headers=auth_headers(owner_login.json()["access_token"]),
    )
    assert banner.status_code == 200, banner.text
    assert banner.json()["console_mode"] is True
    assert "never delivered" in banner.json()["banner"].lower()


def test_missing_message_is_not_found(client) -> None:
    owner_row = signup_tenant(client, email="api-mail-miss@example.com", business_name="Miss Mail")
    missing = client.post(
        f"/api/v1/supplier-messages/{uuid4()}/send",
        headers=auth_headers(owner_row.access_token),
        json={},
    )
    assert missing.status_code == 404
