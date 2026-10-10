from abc import ABC, abstractmethod
from dataclasses import dataclass, replace

from typing import TypeVar

from pydantic import BaseModel

from app.agents.context import AgentContext
from app.agents.errors import ToolCallLimitError
from app.agents.runs import finish_agent_run, start_agent_run
from app.agents.tools import invoke_tool
from app.llm.gateway import CompletionResult, LLMGateway
from app.llm.prompts.registry import get_prompt
from app.llm.providers.base import ChatMessage
from app.models import AgentRun

T = TypeVar("T", bound=BaseModel)


@dataclass
class AgentResult:
    run_id: str
    status: str
    output: dict[str, object] | None
    steps: list[str]


class BaseAgent(ABC):
    name: str
    description: str
    allowed_tools: frozenset[str]
    max_tool_calls: int = 10
    prompt_name: str = "echo"

    def __init__(self, *, gateway: LLMGateway | None = None) -> None:
        self._gateway = gateway
        self._tool_calls = 0
        self._step_ids: list[str] = []
        self._context: AgentContext | None = None
        self._run: AgentRun | None = None

    def attach(self, context: AgentContext) -> None:
        """Bind an existing run (the chat orchestrator) without opening a nested AgentRun."""
        self._tool_calls = 0
        self._step_ids = []
        self._context = context
        self._run = None

    def run(self, task: str, context: AgentContext) -> AgentResult:
        self._tool_calls = 0
        self._step_ids = []
        prompt = get_prompt(self.prompt_name)
        run = start_agent_run(
            context.session,
            business_id=context.business_id,
            agent_name=self.name,
            actor_user_id=context.user_id,
            prompt_name=prompt.name,
            prompt_version=prompt.version,
        )
        bound = replace(context, run_id=run.id)
        self._context = bound
        self._run = run
        try:
            output = self.execute(task, bound)
            finish_agent_run(bound.session, run=run, status="completed")
            return AgentResult(run_id=run.id, status="completed", output=output, steps=self._step_ids)
        except Exception as exc:
            finish_agent_run(bound.session, run=run, status="failed", error_message=str(exc))
            raise

    @abstractmethod
    def execute(self, task: str, context: AgentContext) -> dict[str, object]:
        raise NotImplementedError

    def invoke_tool(self, tool_name: str, arguments: dict[str, object] | BaseModel) -> BaseModel:
        context = self._require_context()
        if self._tool_calls >= self.max_tool_calls:
            raise ToolCallLimitError(self.max_tool_calls)
        self._tool_calls += 1
        result = invoke_tool(
            context.session,
            context=context,
            tool_name=tool_name,
            arguments=arguments,
            allowlist=self.allowed_tools,
        )
        self._step_ids.append(result.step_id)
        return result.output

    def call_llm(self, messages: list[ChatMessage], *, prompt_name: str | None = None) -> CompletionResult:
        context = self._require_context()
        if self._gateway is None:
            self._gateway = LLMGateway(context.session)
        result = self._gateway.complete(
            messages,
            prompt_name=prompt_name or self.prompt_name,
            business_id=context.business_id,
            run_id=context.run_id,
        )
        if result.step_id:
            self._step_ids.append(result.step_id)
        return result

    def call_llm_structured(
        self,
        messages: list[ChatMessage],
        model: type[T],
        *,
        prompt_name: str | None = None,
    ) -> T:
        context = self._require_context()
        if self._gateway is None:
            self._gateway = LLMGateway(context.session)
        return self._gateway.complete_structured(
            messages,
            model,
            prompt_name=prompt_name or self.prompt_name,
            business_id=context.business_id,
            run_id=context.run_id,
        )

    def _require_context(self) -> AgentContext:
        if self._context is None:
            raise RuntimeError("Agent tools require run() to have started.")
        return self._context
