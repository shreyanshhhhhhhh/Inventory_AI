from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models import User
from app.repositories import catalog as catalog_repo
from app.schemas.imports import ImportResultResponse
from app.schemas.catalog import (
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
    ProductCreateRequest,
    ProductListResponse,
    ProductResponse,
    ProductSupplierCreateRequest,
    ProductSupplierResponse,
    ProductSupplierUpdateRequest,
    ProductUpdateRequest,
    SupplierCreateRequest,
    SupplierResponse,
    SupplierUpdateRequest,
)
from app.services import catalog as catalog_service
from app.services.catalog import CatalogError
from app.services.csv_import import (
    PRODUCT_SAMPLE_CSV,
    ImportError,
    import_products_csv,
)

router = APIRouter(tags=["catalog"])


def _require_business(user: User) -> str:
    if user.business_id is None:
        raise HTTPException(status_code=403, detail="This account is not attached to a business.")
    return user.business_id


def _handle_catalog_error(exc: CatalogError) -> HTTPException:
    code = "conflict" if exc.status_code == 409 else "bad_request"
    if exc.status_code == 404:
        code = "not_found"
    return HTTPException(
        status_code=exc.status_code,
        detail={"detail": exc.message, "code": code},
    )


def _product_response_from_row(row: catalog_repo.ProductListRow) -> ProductResponse:
    return ProductResponse(
        id=row.id,
        sku=row.sku,
        name=row.name,
        category_id=row.category_id,
        category_name=row.category_name,
        unit=row.unit,
        cost=row.cost,
        price=row.price,
        reorder_point=row.reorder_point,
        safety_stock=row.safety_stock,
        preferred_supplier_id=row.preferred_supplier_id,
        preferred_supplier_name=row.preferred_supplier_name,
        is_active=row.is_active,
    )


def _product_response_from_model(
    session: Session,
    *,
    business_id: str,
    product_id: str,
) -> ProductResponse:
    row = catalog_repo.get_product_row(session, business_id, product_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    return _product_response_from_row(row)


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories_route(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CategoryResponse]:
    business_id = _require_business(user)
    categories = catalog_service.list_categories(db, business_id=business_id)
    return [CategoryResponse(id=category.id, name=category.name) for category in categories]


@router.post("/categories", response_model=CategoryResponse, status_code=201)
def create_category_route(
    body: CategoryCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CategoryResponse:
    business_id = _require_business(user)
    try:
        category = catalog_service.create_category(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            name=body.name,
        )
    except CatalogError as exc:
        raise _handle_catalog_error(exc) from exc
    return CategoryResponse(id=category.id, name=category.name)


@router.patch("/categories/{category_id}", response_model=CategoryResponse)
def update_category_route(
    category_id: str,
    body: CategoryUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CategoryResponse:
    business_id = _require_business(user)
    try:
        category = catalog_service.update_category(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            category_id=category_id,
            name=body.name,
        )
    except CatalogError as exc:
        raise _handle_catalog_error(exc) from exc
    return CategoryResponse(id=category.id, name=category.name)


@router.delete("/categories/{category_id}", status_code=204)
def delete_category_route(
    category_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    business_id = _require_business(user)
    try:
        catalog_service.delete_category(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            category_id=category_id,
        )
    except CatalogError as exc:
        raise _handle_catalog_error(exc) from exc


@router.get("/suppliers", response_model=list[SupplierResponse])
def list_suppliers_route(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SupplierResponse]:
    business_id = _require_business(user)
    suppliers = catalog_service.list_suppliers(db, business_id=business_id)
    return [
        SupplierResponse(
            id=supplier.id,
            name=supplier.name,
            email=supplier.email,
            phone=supplier.phone,
            lead_time_days=supplier.lead_time_days,
            is_active=supplier.archived_at is None,
        )
        for supplier in suppliers
    ]


@router.post("/suppliers", response_model=SupplierResponse, status_code=201)
def create_supplier_route(
    body: SupplierCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SupplierResponse:
    business_id = _require_business(user)
    try:
        supplier = catalog_service.create_supplier(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            name=body.name,
            email=body.email,
            phone=body.phone,
            lead_time_days=body.lead_time_days,
        )
    except CatalogError as exc:
        raise _handle_catalog_error(exc) from exc
    return SupplierResponse(
        id=supplier.id,
        name=supplier.name,
        email=supplier.email,
        phone=supplier.phone,
        lead_time_days=supplier.lead_time_days,
        is_active=True,
    )


@router.patch("/suppliers/{supplier_id}", response_model=SupplierResponse)
def update_supplier_route(
    supplier_id: str,
    body: SupplierUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SupplierResponse:
    business_id = _require_business(user)
    try:
        supplier = catalog_service.update_supplier(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            supplier_id=supplier_id,
            name=body.name,
            email=body.email,
            phone=body.phone,
            lead_time_days=body.lead_time_days,
        )
    except CatalogError as exc:
        raise _handle_catalog_error(exc) from exc
    return SupplierResponse(
        id=supplier.id,
        name=supplier.name,
        email=supplier.email,
        phone=supplier.phone,
        lead_time_days=supplier.lead_time_days,
        is_active=supplier.archived_at is None,
    )


@router.delete("/suppliers/{supplier_id}", response_model=SupplierResponse)
def archive_supplier_route(
    supplier_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SupplierResponse:
    business_id = _require_business(user)
    try:
        supplier = catalog_service.archive_supplier(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            supplier_id=supplier_id,
        )
    except CatalogError as exc:
        raise _handle_catalog_error(exc) from exc
    return SupplierResponse(
        id=supplier.id,
        name=supplier.name,
        email=supplier.email,
        phone=supplier.phone,
        lead_time_days=supplier.lead_time_days,
        is_active=False,
    )


@router.get("/products", response_model=ProductListResponse)
def list_products_route(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    search: str | None = Query(default=None),
    category_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
) -> ProductListResponse:
    business_id = _require_business(user)
    try:
        items, total = catalog_service.list_products(
            db,
            business_id=business_id,
            search=search,
            category_id=category_id,
            page=page,
            page_size=page_size,
        )
    except CatalogError as exc:
        raise _handle_catalog_error(exc) from exc
    return ProductListResponse(
        items=[_product_response_from_row(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/products", response_model=ProductResponse, status_code=201)
def create_product_route(
    body: ProductCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProductResponse:
    business_id = _require_business(user)
    try:
        product = catalog_service.create_product(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            sku=body.sku,
            name=body.name,
            category_id=body.category_id,
            unit=body.unit,
            cost=body.cost,
            price=body.price,
            reorder_point=body.reorder_point,
            safety_stock=body.safety_stock,
            preferred_supplier_id=body.preferred_supplier_id,
        )
    except CatalogError as exc:
        raise _handle_catalog_error(exc) from exc
    return _product_response_from_model(db, business_id=business_id, product_id=product.id)


@router.patch("/products/{product_id}", response_model=ProductResponse)
def update_product_route(
    product_id: str,
    body: ProductUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProductResponse:
    business_id = _require_business(user)
    try:
        product = catalog_service.update_product(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            product_id=product_id,
            sku=body.sku,
            name=body.name,
            category_id=body.category_id,
            unit=body.unit,
            cost=body.cost,
            price=body.price,
            reorder_point=body.reorder_point,
            safety_stock=body.safety_stock,
            preferred_supplier_id=body.preferred_supplier_id,
        )
    except CatalogError as exc:
        raise _handle_catalog_error(exc) from exc
    return _product_response_from_model(db, business_id=business_id, product_id=product.id)


@router.delete("/products/{product_id}", response_model=ProductResponse)
def archive_product_route(
    product_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProductResponse:
    business_id = _require_business(user)
    try:
        product = catalog_service.archive_product(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            product_id=product_id,
        )
    except CatalogError as exc:
        raise _handle_catalog_error(exc) from exc
    return _product_response_from_model(db, business_id=business_id, product_id=product.id)


@router.get(
    "/products/{product_id}/suppliers",
    response_model=list[ProductSupplierResponse],
)
def list_product_suppliers_route(
    product_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProductSupplierResponse]:
    business_id = _require_business(user)
    try:
        links = catalog_service.list_product_suppliers(
            db,
            business_id=business_id,
            product_id=product_id,
        )
    except CatalogError as exc:
        raise _handle_catalog_error(exc) from exc
    return [
        ProductSupplierResponse(
            id=link.id,
            product_id=link.product_id,
            supplier_id=link.supplier_id,
            supplier_sku=link.supplier_sku,
            unit_cost=link.unit_cost,
            lead_time_days=link.lead_time_days,
            is_preferred=link.is_preferred,
        )
        for link in links
    ]


@router.post(
    "/products/{product_id}/suppliers",
    response_model=ProductSupplierResponse,
    status_code=201,
)
def create_product_supplier_route(
    product_id: str,
    body: ProductSupplierCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProductSupplierResponse:
    business_id = _require_business(user)
    try:
        link = catalog_service.create_product_supplier(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            product_id=product_id,
            supplier_id=body.supplier_id,
            unit_cost=body.unit_cost,
            lead_time_days=body.lead_time_days,
            supplier_sku=body.supplier_sku,
            is_preferred=body.is_preferred,
        )
    except CatalogError as exc:
        raise _handle_catalog_error(exc) from exc
    return ProductSupplierResponse(
        id=link.id,
        product_id=link.product_id,
        supplier_id=link.supplier_id,
        supplier_sku=link.supplier_sku,
        unit_cost=link.unit_cost,
        lead_time_days=link.lead_time_days,
        is_preferred=link.is_preferred,
    )


@router.patch(
    "/product-suppliers/{link_id}",
    response_model=ProductSupplierResponse,
)
def update_product_supplier_route(
    link_id: str,
    body: ProductSupplierUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProductSupplierResponse:
    business_id = _require_business(user)
    try:
        link = catalog_service.update_product_supplier(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            link_id=link_id,
            unit_cost=body.unit_cost,
            lead_time_days=body.lead_time_days,
            supplier_sku=body.supplier_sku,
            is_preferred=body.is_preferred,
        )
    except CatalogError as exc:
        raise _handle_catalog_error(exc) from exc
    return ProductSupplierResponse(
        id=link.id,
        product_id=link.product_id,
        supplier_id=link.supplier_id,
        supplier_sku=link.supplier_sku,
        unit_cost=link.unit_cost,
        lead_time_days=link.lead_time_days,
        is_preferred=link.is_preferred,
    )


@router.delete("/product-suppliers/{link_id}", status_code=204)
def delete_product_supplier_route(
    link_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    business_id = _require_business(user)
    try:
        catalog_service.delete_product_supplier(
            db,
            business_id=business_id,
            actor_user_id=user.id,
            link_id=link_id,
        )
    except CatalogError as exc:
        raise _handle_catalog_error(exc) from exc


@router.get("/products/sample-csv", response_class=PlainTextResponse)
def products_sample_csv_route() -> PlainTextResponse:
    return PlainTextResponse(
        PRODUCT_SAMPLE_CSV,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="catalog-sample.csv"'},
    )


@router.post("/products/import-csv", response_model=ImportResultResponse)
async def import_products_csv_route(
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
        result = import_products_csv(
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
