from sqlalchemy import select

from app.agents.context import AgentContext
from app.llm.gateway import LLMGateway
from app.models import AgentRun, AgentStep
from app.services.auth import signup
from tests.agents.echo_agent import EchoAgent


def test_echo_agent_writes_run_and_steps(db) -> None:
    owner = signup(
        db,
        full_name="Ada Owner",
        email="echo-run@example.com",
        password="correct-horse-1",
        business_name="Echo Shop",
    )
    gateway = LLMGateway(db)
    agent = EchoAgent(gateway=gateway)
    result = agent.run(
        "ping",
        AgentContext(
            session=db,
            business_id=owner.user.business_id,
            user_id=owner.user.id,
            role="owner",
        ),
    )
    assert result.status == "completed"
    assert result.output is not None
    assert result.output["text"] == "ok"
    assert result.output["prompt_version"] == "1"
    run = db.get(AgentRun, result.run_id)
    assert run is not None
    assert run.status == "completed"
    assert run.prompt_name == "echo"
    steps = list(
        db.scalars(select(AgentStep).where(AgentStep.run_id == result.run_id))
    )
    kinds = {step.step_kind for step in steps}
    assert "tool" in kinds
    assert "llm" in kinds
    assert len(result.steps) == len(steps)
