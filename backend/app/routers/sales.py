from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models import User
from app.schemas.imports import ImportResultResponse
from app.services.csv_import import (
    SALES_SAMPLE_CSV,
    ImportError,
    import_sales_csv,
)

router = APIRouter(prefix="/sales", tags=["sales"])


def _require_business(user: User) -> str:
    if user.business_id is None:
        raise HTTPException(status_code=403, detail="This account is not attached to a business.")
    return user.business_id


@router.get("/sample-csv", response_class=PlainTextResponse)
def sales_sample_csv_route() -> PlainTextResponse:
    return PlainTextResponse(
        SALES_SAMPLE_CSV,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="sales-sample.csv"'},
    )


@router.post("/import-csv", response_model=ImportResultResponse)
async def import_sales_csv_route(
    file: UploadFile = File(...),
    skip_errors: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImportResultResponse | JSONResponse:
    business_id = _require_business(user)
    raw = await file.read()
    try:
        csv_text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail={"detail": "CSV must be UTF-8 encoded.", "code": "bad_request"},
        ) from exc
    try:
        result = import_sales_csv(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            csv_text=csv_text,
            skip_errors=skip_errors,
        )
    except ImportError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"detail": exc.message, "code": exc.code},
        ) from exc

    payload = ImportResultResponse.model_validate(result.to_dict())
    if not result.success and not skip_errors:
        return JSONResponse(status_code=400, content=payload.model_dump())
    return payload
