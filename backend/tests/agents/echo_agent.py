from app.agents.base import BaseAgent
from app.llm.prompts.registry import get_prompt
from app.llm.providers.base import ChatMessage
from app.llm.security import DATA_BLOCK_INSTRUCTIONS, wrap_untrusted


class EchoAgent(BaseAgent):
    name = "echo"
    description = "Test-only agent that reads stock and calls the fake LLM."
    allowed_tools = frozenset({"get_stock", "list_low_stock"})
    prompt_name = "echo"

    def execute(self, task: str, context) -> dict[str, object]:
        stock = self.invoke_tool("get_stock", {})
        names = [item.product_name for item in stock.items]
        prompt = get_prompt(self.prompt_name)
        completion = self.call_llm(
            [
                ChatMessage(role="system", content=f"{prompt.template}\n{DATA_BLOCK_INSTRUCTIONS}"),
                ChatMessage(
                    role="user",
                    content=wrap_untrusted({"task": task, "product_names": names}, label="task"),
                ),
            ]
        )
        return {
            "text": completion.text,
            "product_names": names,
            "prompt_name": completion.prompt_name,
            "prompt_version": completion.prompt_version,
        }
