from app.core.errors import AppError


class OrchestratorError(AppError):
    def __init__(self, detail: str, *, code: str, status_code: int = 400) -> None:
        super().__init__(detail, code=code, status_code=status_code)
