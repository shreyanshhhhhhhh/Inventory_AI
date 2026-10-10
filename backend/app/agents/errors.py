from app.core.errors import AppError


class AgentError(AppError):
    def __init__(self, detail: str, *, code: str, status_code: int = 400) -> None:
        super().__init__(detail, code=code, status_code=status_code)


class ToolNotAllowedError(AgentError):
    def __init__(self, tool_name: str) -> None:
        super().__init__(
            f"Tool '{tool_name}' is not on this agent's allowlist.",
            code="tool_not_allowed",
            status_code=403,
        )


class ToolRoleError(AgentError):
    def __init__(self, tool_name: str) -> None:
        super().__init__(
            f"Tool '{tool_name}' is not allowed for this role.",
            code="tool_forbidden",
            status_code=403,
        )


class ToolCallLimitError(AgentError):
    def __init__(self, limit: int) -> None:
        super().__init__(
            f"This agent reached its max tool call limit ({limit}).",
            code="tool_call_limit",
            status_code=400,
        )
