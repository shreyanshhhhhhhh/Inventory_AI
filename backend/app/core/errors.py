from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


def error_code_for_status(status_code: int) -> str:
    mapping = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        500: "internal_error",
    }
    return mapping.get(status_code, "error")


class AppError(Exception):
    def __init__(self, detail: str, *, code: str, status_code: int = 400) -> None:
        self.detail = detail
        self.code = code
        self.status_code = status_code
        super().__init__(detail)


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )


async def http_error_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "detail" in exc.detail and "code" in exc.detail:
        content = exc.detail
    elif isinstance(exc.detail, str):
        content = {
            "detail": exc.detail,
            "code": error_code_for_status(exc.status_code),
        }
    else:
        content = {
            "detail": "Request failed.",
            "code": error_code_for_status(exc.status_code),
        }
    return JSONResponse(status_code=exc.status_code, content=content)
