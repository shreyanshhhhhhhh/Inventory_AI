import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Location, Product, Supplier
from app.models.types import new_id, utcnow
from app.repositories import inventory as inventory_repo
from app.services.audit import log_action
from app.services.catalog import _set_preferred_supplier
from app.services.inventory import InventoryError, post_movement
from app.services.purchase_orders import create_po, transition_po


DEMO_SEED = 42
PRODUCT_COUNT = 100
DEMO_SECOND_LOCATION = "Backroom"
TRANSFER_PRODUCT_COUNT = 15
SUPPLIER_SPECS = [
    ("Green Valley Produce", 2),
    ("Summit Beverage Co.", 3),
    ("Coastal Dairy", 1),
    ("Metro Grocery Wholesale", 5),
    ("Harbor Household Supply", 7),
]
CATEGORY_NAMES = [
    "Produce",
    "Dairy",
    "Beverages",
    "Grocery",
    "Household",
    "Bakery",
    "Frozen",
    "Snacks",
]


class DemoSeedError(Exception):
    def __init__(self, message: str, *, status_code: int = 409, code: str = "conflict") -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


def _audit_create(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    entity_type: str,
    entity_id: str,
    data: dict[str, object],
) -> None:
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action=f"{entity_type}.create",
        entity_type=entity_type,
        entity_id=entity_id,
        before_data=None,
        after_data={"id": entity_id, **data, "source": "demo_data"},
    )


def _product_count(session: Session, business_id: str) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(Product).where(Product.business_id == business_id)
        )
        or 0
    )


def load_demo_data(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
) -> dict[str, object]:
    if _product_count(session, business_id) > 0:
        raise DemoSeedError(
            "Demo data can only be loaded into an empty catalog.",
            status_code=409,
            code="demo_already_loaded",
        )

    rng = random.Random(DEMO_SEED)
    locations = inventory_repo.list_locations(session, business_id)
    if not locations:
        raise DemoSeedError("At least one location is required.", code="bad_request")
    default_location = next((loc for loc in locations if loc.is_default), locations[0])

    today = utcnow().date()
    start_date = today - timedelta(days=364)
    opening_at = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)

    categories: list[Category] = []
    for name in CATEGORY_NAMES:
        category = Category(id=new_id(), business_id=business_id, name=name)
        session.add(category)
        categories.append(category)
        _audit_create(
            session,
            business_id=business_id,
            actor_user_id=actor_user_id,
            entity_type="category",
            entity_id=category.id,
            data={"name": name},
        )
    session.flush()

    suppliers: list[Supplier] = []
    for name, lead_time in SUPPLIER_SPECS:
        supplier = Supplier(
            id=new_id(),
            business_id=business_id,
            name=name,
            lead_time_days=lead_time,
        )
        session.add(supplier)
        suppliers.append(supplier)
        _audit_create(
            session,
            business_id=business_id,
            actor_user_id=actor_user_id,
            entity_type="supplier",
            entity_id=supplier.id,
            data={"name": name, "lead_time_days": lead_time},
        )
    session.flush()

    products: list[Product] = []
    on_hand: dict[str, Decimal] = {}
    for index in range(1, PRODUCT_COUNT + 1):
        category = categories[(index - 1) % len(categories)]
        supplier = suppliers[(index - 1) % len(suppliers)]
        sku = f"DEMO-{index:03d}"
        cost = Decimal(rng.randint(75, 1250)) / Decimal(100)
        price = (cost * Decimal("1.35")).quantize(Decimal("0.01"))
        reorder_point = Decimal(str(rng.randint(5, 25)))
        product = Product(
            id=new_id(),
            business_id=business_id,
            sku=sku,
            name=f"Demo {category.name} Item {index:03d}",
            category_id=category.id,
            unit="each",
            cost=cost,
            price=price,
            reorder_point=reorder_point,
            safety_stock=Decimal(str(rng.randint(0, 5))),
        )
        session.add(product)
        session.flush()
        _set_preferred_supplier(
            session,
            business_id=business_id,
            product=product,
            supplier_id=supplier.id,
            unit_cost=cost,
            lead_time_days=supplier.lead_time_days,
        )
        products.append(product)
        _audit_create(
            session,
            business_id=business_id,
            actor_user_id=actor_user_id,
            entity_type="product",
            entity_id=product.id,
            data={
                "sku": sku,
                "name": product.name,
                "cost": str(cost),
                "price": str(price),
                "preferred_supplier_id": supplier.id,
            },
        )

        starting_stock = Decimal(rng.randint(30, 180))
        on_hand[product.id] = starting_stock
        post_movement(
            session,
            business_id=business_id,
            actor_user_id=actor_user_id,
            product_id=product.id,
            location_id=default_location.id,
            movement_type="receipt",
            quantity=starting_stock,
            note="Demo starting stock",
            occurred_at=opening_at,
            commit=False,
        )

    stock_movements_created = PRODUCT_COUNT
    sale_movements_created = 0
    spike_days = set(rng.sample(range(365), 5))

    for day_offset in range(365):
        current_day = start_date + timedelta(days=day_offset)
        occurred_at = datetime.combine(current_day, datetime.min.time()).replace(
            tzinfo=timezone.utc
        )
        weekday = current_day.weekday()
        weekend_boost = 1.4 if weekday >= 4 else 1.0
        seasonal = 1.0 + 0.25 * abs(((day_offset / 365) * 6.28) - 3.14) / 3.14
        spike = 2.5 if day_offset in spike_days else 1.0
        daily_product_count = int(18 * weekend_boost * seasonal * spike)
        daily_product_count = max(8, min(daily_product_count, 35))
        day_products = rng.sample(products, daily_product_count)

        for product in day_products:
            quantity = Decimal(max(1, int(rng.randint(1, 4) * spike)))
            if on_hand[product.id] < quantity:
                # A year of sales outruns any single opening balance; simulate deliveries.
                restock = Decimal(rng.randint(60, 160))
                post_movement(
                    session,
                    business_id=business_id,
                    actor_user_id=actor_user_id,
                    product_id=product.id,
                    location_id=default_location.id,
                    movement_type="receipt",
                    quantity=restock,
                    note="Demo restock",
                    occurred_at=occurred_at,
                    commit=False,
                )
                on_hand[product.id] += restock
                stock_movements_created += 1
            try:
                post_movement(
                    session,
                    business_id=business_id,
                    actor_user_id=actor_user_id,
                    product_id=product.id,
                    location_id=default_location.id,
                    movement_type="sale",
                    quantity=quantity,
                    note="Demo sale",
                    occurred_at=occurred_at,
                    commit=False,
                )
                sale_movements_created += 1
                on_hand[product.id] -= quantity
            except InventoryError:
                continue

    locations_created = 0
    active_locations = [loc for loc in locations if loc.archived_at is None]
    if len(active_locations) < 2:
        backroom = Location(
            id=new_id(),
            business_id=business_id,
            name=DEMO_SECOND_LOCATION,
            is_default=False,
        )
        session.add(backroom)
        session.flush()
        locations_created = 1
        _audit_create(
            session,
            business_id=business_id,
            actor_user_id=actor_user_id,
            entity_type="location",
            entity_id=backroom.id,
            data={"name": backroom.name, "is_default": False},
        )
        second_location = backroom
    else:
        second_location = next(loc for loc in active_locations if loc.id != default_location.id)

    transfer_at = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    for product in products[:TRANSFER_PRODUCT_COUNT]:
        transfer_quantity = (on_hand[product.id] / 3).to_integral_value(rounding="ROUND_FLOOR")
        if transfer_quantity < 1:
            continue
        post_movement(
            session,
            business_id=business_id,
            actor_user_id=actor_user_id,
            product_id=product.id,
            location_id=default_location.id,
            movement_type="transfer",
            quantity=transfer_quantity,
            destination_location_id=second_location.id,
            note="Demo transfer",
            occurred_at=transfer_at,
            commit=False,
        )
        on_hand[product.id] -= transfer_quantity
        stock_movements_created += 2

    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="onboarding.load_demo_data",
        entity_type="business",
        entity_id=business_id,
        before_data=None,
        after_data={
            "products_created": PRODUCT_COUNT,
            "suppliers_created": len(SUPPLIER_SPECS),
            "categories_created": len(CATEGORY_NAMES),
            "locations_created": locations_created,
        },
    )

    session.commit()

    purchase_orders_created = 0
    sample_products = products[:12]
    po_specs = [
        ("draft", None),
        ("approved", "approve"),
        ("sent", "send"),
        ("received", "receive"),
        ("cancelled", "cancel"),
    ]

    for status_target, transition in po_specs:
        order = create_po(
            session,
            business_id=business_id,
            actor_user_id=actor_user_id,
            supplier_id=suppliers[purchase_orders_created % len(suppliers)].id,
            expected_date=today + timedelta(days=7 + purchase_orders_created),
            location_id=default_location.id,
            notes=f"Demo PO ({status_target})",
            line_items=[
                {
                    "product_id": sample_products[i].id,
                    "quantity": Decimal(str(rng.randint(5, 20))),
                    "unit_cost": sample_products[i].cost,
                }
                for i in range(2)
            ],
        )
        purchase_orders_created += 1
        po_id = str(order["id"])
        if transition == "approve":
            transition_po(
                session,
                business_id=business_id,
                actor_user_id=actor_user_id,
                purchase_order_id=po_id,
                action="approve",
                actor_role="owner",
            )
        elif transition == "send":
            transition_po(
                session,
                business_id=business_id,
                actor_user_id=actor_user_id,
                purchase_order_id=po_id,
                action="approve",
                actor_role="owner",
            )
            transition_po(
                session,
                business_id=business_id,
                actor_user_id=actor_user_id,
                purchase_order_id=po_id,
                action="send",
                actor_role="owner",
            )
        elif transition == "receive":
            transition_po(
                session,
                business_id=business_id,
                actor_user_id=actor_user_id,
                purchase_order_id=po_id,
                action="approve",
                actor_role="owner",
            )
            transition_po(
                session,
                business_id=business_id,
                actor_user_id=actor_user_id,
                purchase_order_id=po_id,
                action="send",
                actor_role="owner",
            )
            transition_po(
                session,
                business_id=business_id,
                actor_user_id=actor_user_id,
                purchase_order_id=po_id,
                action="receive",
                actor_role="owner",
            )
        elif transition == "cancel":
            transition_po(
                session,
                business_id=business_id,
                actor_user_id=actor_user_id,
                purchase_order_id=po_id,
                action="approve",
                actor_role="owner",
            )
            transition_po(
                session,
                business_id=business_id,
                actor_user_id=actor_user_id,
                purchase_order_id=po_id,
                action="cancel",
                actor_role="owner",
            )

    return {
        "products_created": PRODUCT_COUNT,
        "suppliers_created": len(SUPPLIER_SPECS),
        "categories_created": len(CATEGORY_NAMES),
        "stock_movements_created": stock_movements_created,
        "sale_movements_created": sale_movements_created,
        "purchase_orders_created": purchase_orders_created,
        "message": "Demo data loaded.",
    }
