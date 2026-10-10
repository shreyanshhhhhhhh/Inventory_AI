from decimal import Decimal

from app.services.catalog import create_product, create_product_supplier, create_supplier
from app.services.explainer import parse_whatif_query, run_whatif
from app.services.inventory import post_movement
from app.services.replenishment import reorder_recommendations, whatif_compare
from app.repositories import inventory as inventory_repo
from tests.orchestrator.helpers import owner


def _location_id(db, business_id: str) -> str:
    return inventory_repo.list_locations(db, business_id)[0].id


def test_whatif_demand_percent_matches_recommendation_math(db) -> None:
    signed = owner(db, "explainer-svc@example.com", "Explainer Svc")
    business_id = signed.user.business_id
    supplier = create_supplier(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        name="Mill",
        email="mill@example.com",
        phone=None,
        lead_time_days=4,
    )
    product = create_product(
        db,
        business_id=business_id,
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
        business_id=business_id,
        actor_user_id=signed.user.id,
        product_id=product.id,
        supplier_id=supplier.id,
        unit_cost=Decimal("1.50"),
        lead_time_days=4,
        is_preferred=True,
    )
    location_id = _location_id(db, business_id)
    post_movement(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        product_id=product.id,
        location_id=location_id,
        movement_type="receipt",
        quantity=Decimal("20"),
        note="Opening",
    )
    post_movement(
        db,
        business_id=business_id,
        actor_user_id=signed.user.id,
        product_id=product.id,
        location_id=location_id,
        movement_type="sale",
        quantity=Decimal("6"),
    )
    baseline = reorder_recommendations(db, business_id=business_id)
    assert baseline
    compare = whatif_compare(
        db,
        business_id=business_id,
        demand_pct=Decimal("20"),
        product_id=product.id,
    )
    assert compare["answerable"] is True
    item = compare["items"][0]
    assert Decimal(str(item["before"]["recommended_quantity"])) == Decimal(
        str(baseline[0]["recommended_quantity"])
    )
    assert Decimal(str(item["after"]["forecast_units"])) == Decimal(
        str(item["before"]["forecast_units"])
    ) * Decimal("1.20")
    via_query = run_whatif(db, business_id=business_id, query="demand up 20%", product_id=product.id)
    assert via_query["items"][0]["after"]["recommended_quantity"] == item["after"]["recommended_quantity"]
    delay = whatif_compare(
        db,
        business_id=business_id,
        delay_days=5,
        product_id=product.id,
    )
    assert Decimal(str(delay["items"][0]["after"]["recommended_quantity"])) >= Decimal(
        str(delay["items"][0]["before"]["recommended_quantity"])
    )
    parsed = parse_whatif_query("lead time 10 days")
    assert parsed["lead_time_days"] == 10
