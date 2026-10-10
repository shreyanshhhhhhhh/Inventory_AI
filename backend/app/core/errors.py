from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


def error_code_for_status(status_code: int) -> str:
    mapping = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        429: "rate_limited",
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
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)


def _validation_message(error: dict[str, object]) -> str:
    message = str(error.get("msg", "Invalid value."))
    message = message.removeprefix("Value error, ")
    location = [str(part) for part in error.get("loc", ()) if part not in ("body", "query", "path")]
    if location and message[:1].islower():
        return f"{'.'.join(location)}: {message}"
    return message


async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = list(exc.errors())
    detail = _validation_message(errors[0]) if errors else "Request is invalid."
    return JSONResponse(
        status_code=422,
        content={
            "detail": detail,
            "code": "validation_error",
            "errors": [
                {"loc": [str(part) for part in error.get("loc", ())], "msg": str(error.get("msg", ""))}
                for error in errors
            ],
        },
    )
