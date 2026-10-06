from decimal import Decimal

from app.agents.context import AgentContext
from app.agents.runs import start_agent_run
from app.agents.tools import GetStockOutput, invoke_tool
from app.repositories import inventory as inventory_repo
from app.services.auth import signup
from app.services.catalog import create_product
from app.services.inventory import post_movement


def test_tools_are_scoped_to_context_business(db) -> None:
    owner_a = signup(
        db,
        full_name="Ada Owner",
        email="tenant-a@example.com",
        password="correct-horse-1",
        business_name="Shop A",
    )
    owner_b = signup(
        db,
        full_name="Bea Owner",
        email="tenant-b@example.com",
        password="correct-horse-1",
        business_name="Shop B",
    )
    product_b = create_product(
        db,
        business_id=owner_b.user.business_id,
        actor_user_id=owner_b.user.id,
        sku="SECRET-1",
        name="Secret SKU",
        category_id=None,
        unit="each",
        cost=Decimal("1.00"),
        price=Decimal("2.00"),
        reorder_point=Decimal("1"),
        safety_stock=Decimal("0"),
        preferred_supplier_id=None,
    )
    location_b = inventory_repo.list_locations(db, owner_b.user.business_id)[0].id
    post_movement(
        db,
        business_id=owner_b.user.business_id,
        actor_user_id=owner_b.user.id,
        product_id=product_b.id,
        location_id=location_b,
        movement_type="receipt",
        quantity=Decimal("9"),
        note="B stock",
    )
    run = start_agent_run(
        db,
        business_id=owner_a.user.business_id,
        agent_name="echo",
        actor_user_id=owner_a.user.id,
    )
    context = AgentContext(
        session=db,
        business_id=owner_a.user.business_id,
        user_id=owner_a.user.id,
        role="owner",
        run_id=run.id,
    )
    result = invoke_tool(
        db,
        context=context,
        tool_name="get_stock",
        arguments={},
        allowlist=frozenset({"get_stock"}),
    )
    output = result.output
    assert isinstance(output, GetStockOutput)
    assert all(item.sku != "SECRET-1" for item in output.items)
    assert all(item.product_name != "Secret SKU" for item in output.items)
