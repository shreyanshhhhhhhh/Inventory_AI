from decimal import Decimal

import pytest

from app.agents.context import AgentContext
from app.agents.errors import ToolNotAllowedError, ToolRoleError
from app.agents.runs import start_agent_run
from app.agents.tools import invoke_tool
from app.services.agent_suggestions import list_suggestions
from app.services.auth import signup
from app.services.team import create_staff_user


def test_disallowed_tool_is_rejected_before_handler(db) -> None:
    owner = signup(
        db,
        full_name="Ada Owner",
        email="tools-allow@example.com",
        password="correct-horse-1",
        business_name="Allow Shop",
    )
    run = start_agent_run(
        db,
        business_id=owner.user.business_id,
        agent_name="echo",
        actor_user_id=owner.user.id,
    )
    context = AgentContext(
        session=db,
        business_id=owner.user.business_id,
        user_id=owner.user.id,
        role="owner",
        run_id=run.id,
    )
    with pytest.raises(ToolNotAllowedError) as exc:
        invoke_tool(
            db,
            context=context,
            tool_name="create_draft_po_suggestion",
            arguments={
                "supplier_id": "x",
                "lines": [{"product_id": "y", "quantity": Decimal("1")}],
            },
            allowlist=frozenset({"get_stock"}),
        )
    assert exc.value.code == "tool_not_allowed"
    assert list_suggestions(db, business_id=owner.user.business_id) == []


def test_write_tools_require_owner(db) -> None:
    owner = signup(
        db,
        full_name="Ada Owner",
        email="tools-role@example.com",
        password="correct-horse-1",
        business_name="Role Shop",
    )
    staff = create_staff_user(
        db,
        business_id=owner.user.business_id,
        actor_user_id=owner.user.id,
        full_name="Sam Staff",
        email="staff-role@example.com",
        temporary_password="correct-horse-1",
    )
    run = start_agent_run(
        db,
        business_id=owner.user.business_id,
        agent_name="echo",
        actor_user_id=staff["id"],
    )
    context = AgentContext(
        session=db,
        business_id=owner.user.business_id,
        user_id=staff["id"],
        role="staff",
        run_id=run.id,
    )
    with pytest.raises(ToolRoleError):
        invoke_tool(
            db,
            context=context,
            tool_name="create_suggestion",
            arguments={"title": "Nope", "summary": "Staff cannot write."},
            allowlist=frozenset({"create_suggestion"}),
        )
    assert list_suggestions(db, business_id=owner.user.business_id) == []
