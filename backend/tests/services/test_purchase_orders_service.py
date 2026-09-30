from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.security import hash_password
from app.models import AuditLog, StockMovement, User
from app.models.types import new_id
from app.repositories import inventory as inventory_repo
from app.services.auth import signup
from app.services.catalog import create_product, create_supplier
from app.services.inventory import post_movement
from app.services.purchase_orders import (
    PurchaseOrderError,
    create_po,
    get_po,
    list_pos,
    transition_po,
)


def _owner(db):
    return signup(
        db,
        full_name="Ada Owner",
        email="po-owner@example.com",
        password="correct-horse-1",
        business_name="PO Shop",
    )


def _other_owner(db):
    return signup(
        db,
        full_name="Bea Owner",
        email="po-other@example.com",
        password="correct-horse-1",
        business_name="Other PO Shop",
    )


def _staff_user(db, *, business_id: str) -> User:
    user = User(
        id=new_id(),
        business_id=business_id,
        email="po-staff@example.com",
        password_hash=hash_password("staff-pass-123"),
        full_name="Staff User",
        role="staff",
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def _default_location_id(db, business_id: str) -> str:
    return inventory_repo.list_locations(db, business_id)[0].id


def _seed_catalog(db, owner) -> tuple[str, str, str]:
    business_id = owner.user.business_id
    supplier = create_supplier(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        name="Green Valley",
        email=None,
        phone=None,
        lead_time_days=2,
    )
    product = create_product(
        db,
        business_id=business_id,
        actor_user_id=owner.user.id,
        sku="SKU-PO-1",
        name="Apples",
        category_id=None,
        unit="each",
        cost=Decimal("1.50"),
        price=Decimal("2.99"),
        reorder_point=Decimal("10"),
        safety_stock=Decimal("0"),
        preferred_supplier_id=None,
    )
    return supplier.id, product.id, _default_location_id(db, business_id)


def _create_draft_po(db, owner, *, supplier_id: str, product_id: str) -> str:
    order = create_po(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        supplier_id=supplier_id,
        expected_date=date(2026, 10, 15),
        location_id=None,
        notes="Weekly restock",
        line_items=[
            {
                "product_id": product_id,
                "quantity": Decimal("12"),
                "unit_cost": None,
            }
        ],
    )
    return order["id"]


def test_full_purchase_order_lifecycle(db) -> None:
    owner = _owner(db)
    supplier_id, product_id, _ = _seed_catalog(db, owner)
    po_id = _create_draft_po(db, owner, supplier_id=supplier_id, product_id=product_id)

    approved = transition_po(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        purchase_order_id=po_id,
        action="approve",
        actor_role="owner",
    )
    assert approved["status"] == "approved"

    sent = transition_po(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        purchase_order_id=po_id,
        action="send",
        actor_role="owner",
    )
    assert sent["status"] == "sent"
    assert sent["ordered_at"] is not None

    received = transition_po(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        purchase_order_id=po_id,
        action="receive",
        actor_role="owner",
    )
    assert received["status"] == "received"
    assert Decimal(received["total"]) == Decimal("18.00")


def test_invalid_transitions_return_conflict(db) -> None:
    owner = _owner(db)
    supplier_id, product_id, _ = _seed_catalog(db, owner)
    po_id = _create_draft_po(db, owner, supplier_id=supplier_id, product_id=product_id)

    with pytest.raises(PurchaseOrderError) as exc:
        transition_po(
            db,
            business_id=owner.user.business_id,
            actor_user_id=owner.user.id,
            purchase_order_id=po_id,
            action="send",
            actor_role="owner",
        )
    assert exc.value.status_code == 409


def test_staff_cannot_approve(db) -> None:
    owner = _owner(db)
    supplier_id, product_id, _ = _seed_catalog(db, owner)
    staff = _staff_user(db, business_id=owner.user.business_id)
    po_id = _create_draft_po(db, owner, supplier_id=supplier_id, product_id=product_id)

    with pytest.raises(PurchaseOrderError) as exc:
        transition_po(
            db,
            business_id=owner.user.business_id,
            actor_user_id=staff.id,
            purchase_order_id=po_id,
            action="approve",
            actor_role="staff",
        )
    assert exc.value.status_code == 403


def test_receive_creates_movements_and_increases_stock(db) -> None:
    owner = _owner(db)
    supplier_id, product_id, location_id = _seed_catalog(db, owner)
    po_id = _create_draft_po(db, owner, supplier_id=supplier_id, product_id=product_id)

    for action in ("approve", "send", "receive"):
        transition_po(
            db,
            business_id=owner.user.business_id,
            actor_user_id=owner.user.id,
            purchase_order_id=po_id,
            action=action,
            actor_role="owner",
        )

    on_hand = inventory_repo.get_on_hand(
        db,
        business_id=owner.user.business_id,
        product_id=product_id,
        location_id=location_id,
    )
    assert on_hand == Decimal("12")
    assert (
        db.scalar(
            select(func.count()).select_from(StockMovement).where(
                StockMovement.movement_type == "purchase_receipt"
            )
        )
        == 1
    )


def test_receive_rolls_back_on_failure(db) -> None:
    owner = _owner(db)
    supplier_id, product_id, location_id = _seed_catalog(db, owner)
    product_two = create_product(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        sku="SKU-PO-2",
        name="Bananas",
        category_id=None,
        unit="each",
        cost=Decimal("0.75"),
        price=Decimal("1.49"),
        reorder_point=Decimal("5"),
        safety_stock=Decimal("0"),
        preferred_supplier_id=None,
    )
    order = create_po(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        supplier_id=supplier_id,
        expected_date=date(2026, 10, 20),
        location_id=location_id,
        notes=None,
        line_items=[
            {"product_id": product_id, "quantity": Decimal("4"), "unit_cost": Decimal("1.50")},
            {"product_id": product_two.id, "quantity": Decimal("6"), "unit_cost": Decimal("0.75")},
        ],
    )
    po_id = order["id"]
    detail = get_po(db, business_id=owner.user.business_id, purchase_order_id=po_id)
    second_line_id = detail["line_items"][1]["id"]

    post_movement(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        product_id=product_two.id,
        location_id=location_id,
        movement_type="purchase_receipt",
        quantity=Decimal("6"),
        purchase_order_item_id=second_line_id,
        commit=True,
    )

    transition_po(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        purchase_order_id=po_id,
        action="approve",
        actor_role="owner",
    )
    transition_po(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        purchase_order_id=po_id,
        action="send",
        actor_role="owner",
    )

    with pytest.raises(PurchaseOrderError):
        transition_po(
            db,
            business_id=owner.user.business_id,
            actor_user_id=owner.user.id,
            purchase_order_id=po_id,
            action="receive",
            actor_role="owner",
        )

    po = get_po(db, business_id=owner.user.business_id, purchase_order_id=po_id)
    assert po["status"] == "sent"
    assert (
        db.scalar(
            select(func.count()).select_from(StockMovement).where(
                StockMovement.movement_type == "purchase_receipt",
                StockMovement.purchase_order_item_id != second_line_id,
            )
        )
        == 0
    )


def test_total_calculation(db) -> None:
    owner = _owner(db)
    supplier_id, product_id, _ = _seed_catalog(db, owner)
    po_id = _create_draft_po(db, owner, supplier_id=supplier_id, product_id=product_id)
    detail = get_po(db, business_id=owner.user.business_id, purchase_order_id=po_id)
    assert Decimal(detail["total"]) == Decimal("18.00")
    assert Decimal(detail["line_items"][0]["line_total"]) == Decimal("18.00")


def test_tenant_isolation(db) -> None:
    owner = _owner(db)
    other = _other_owner(db)
    supplier_id, product_id, _ = _seed_catalog(db, owner)
    po_id = _create_draft_po(db, owner, supplier_id=supplier_id, product_id=product_id)

    items, total = list_pos(db, business_id=other.user.business_id, page=1, page_size=10)
    assert total == 0
    assert items == []

    with pytest.raises(PurchaseOrderError) as exc:
        get_po(db, business_id=other.user.business_id, purchase_order_id=po_id)
    assert exc.value.status_code == 404
