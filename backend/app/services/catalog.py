from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Category, Product, ProductSupplier, Supplier
from app.models.types import new_id, utcnow
from app.repositories import catalog as catalog_repo
from app.services.audit import write_audit


class CatalogError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _decimal_dict(data: dict[str, object]) -> dict[str, object]:
    serialized: dict[str, object] = {}
    for key, value in data.items():
        if isinstance(value, Decimal):
            serialized[key] = str(value)
        else:
            serialized[key] = value
    return serialized


def _category_payload(category: Category) -> dict[str, object]:
    return {"id": category.id, "name": category.name}


def _supplier_payload(supplier: Supplier) -> dict[str, object]:
    return {
        "id": supplier.id,
        "name": supplier.name,
        "email": supplier.email,
        "phone": supplier.phone,
        "lead_time_days": supplier.lead_time_days,
        "is_active": supplier.archived_at is None,
    }


def _product_payload(product: Product) -> dict[str, object]:
    return _decimal_dict(
        {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "description": product.description,
            "category_id": product.category_id,
            "unit": product.unit,
            "cost": product.cost,
            "price": product.price,
            "reorder_point": product.reorder_point,
            "safety_stock": product.safety_stock,
            "is_active": product.archived_at is None,
        }
    )


def _product_supplier_payload(link: ProductSupplier) -> dict[str, object]:
    return _decimal_dict(
        {
            "id": link.id,
            "product_id": link.product_id,
            "supplier_id": link.supplier_id,
            "supplier_sku": link.supplier_sku,
            "unit_cost": link.unit_cost,
            "lead_time_days": link.lead_time_days,
            "is_preferred": link.is_preferred,
        }
    )


def _require_non_negative(value: Decimal | None, label: str) -> None:
    if value is not None and value < 0:
        raise CatalogError(f"{label} must be 0 or greater.")


def _get_category_or_error(
    session: Session,
    *,
    business_id: str,
    category_id: str,
) -> Category:
    category = catalog_repo.get_category(session, business_id, category_id)
    if category is None:
        raise CatalogError("Category not found.", 404)
    return category


def _get_supplier_or_error(
    session: Session,
    *,
    business_id: str,
    supplier_id: str,
    active_only: bool = True,
) -> Supplier:
    supplier = catalog_repo.get_supplier(session, business_id, supplier_id)
    if supplier is None:
        raise CatalogError("Supplier not found.", 404)
    if active_only and supplier.archived_at is not None:
        raise CatalogError("Supplier is archived.", 404)
    return supplier


def _get_product_or_error(
    session: Session,
    *,
    business_id: str,
    product_id: str,
    active_only: bool = False,
) -> Product:
    product = catalog_repo.get_product(session, business_id, product_id)
    if product is None:
        raise CatalogError("Product not found.", 404)
    if active_only and product.archived_at is not None:
        raise CatalogError("Product is archived.", 404)
    return product


def _set_preferred_supplier(
    session: Session,
    *,
    business_id: str,
    product: Product,
    supplier_id: str,
    unit_cost: Decimal,
    lead_time_days: int,
) -> None:
    _get_supplier_or_error(session, business_id=business_id, supplier_id=supplier_id)
    catalog_repo.clear_preferred_supplier(session, business_id, product.id)
    existing = catalog_repo.get_product_supplier_link(
        session,
        business_id,
        product.id,
        supplier_id,
    )
    if existing is None:
        session.add(
            ProductSupplier(
                id=new_id(),
                business_id=business_id,
                product_id=product.id,
                supplier_id=supplier_id,
                unit_cost=unit_cost,
                lead_time_days=lead_time_days,
                is_preferred=True,
            )
        )
    else:
        existing.unit_cost = unit_cost
        existing.lead_time_days = lead_time_days
        existing.is_preferred = True


def list_categories(session: Session, *, business_id: str) -> list[Category]:
    return catalog_repo.list_categories(session, business_id)


def create_category(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    name: str,
) -> Category:
    category = Category(id=new_id(), business_id=business_id, name=name.strip())
    session.add(category)
    write_audit(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="category.create",
        entity_type="category",
        entity_id=category.id,
        before_data=None,
        after_data=_category_payload(category),
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise CatalogError("A category with this name already exists.", 409) from exc
    session.refresh(category)
    return category


def update_category(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    category_id: str,
    name: str,
) -> Category:
    category = _get_category_or_error(session, business_id=business_id, category_id=category_id)
    before = _category_payload(category)
    category.name = name.strip()
    write_audit(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="category.update",
        entity_type="category",
        entity_id=category.id,
        before_data=before,
        after_data=_category_payload(category),
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise CatalogError("A category with this name already exists.", 409) from exc
    session.refresh(category)
    return category


def delete_category(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    category_id: str,
) -> None:
    category = _get_category_or_error(session, business_id=business_id, category_id=category_id)
    before = _category_payload(category)
    write_audit(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="category.delete",
        entity_type="category",
        entity_id=category.id,
        before_data=before,
        after_data=None,
    )
    session.delete(category)
    session.commit()


def list_suppliers(
    session: Session,
    *,
    business_id: str,
    include_archived: bool = False,
) -> list[Supplier]:
    return catalog_repo.list_suppliers(session, business_id, active_only=not include_archived)


def restore_supplier(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    supplier_id: str,
) -> Supplier:
    supplier = _get_supplier_or_error(
        session, business_id=business_id, supplier_id=supplier_id, active_only=False
    )
    if supplier.archived_at is None:
        return supplier
    before = _supplier_payload(supplier)
    supplier.archived_at = None
    write_audit(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="supplier.restore",
        entity_type="supplier",
        entity_id=supplier.id,
        before_data=before,
        after_data=_supplier_payload(supplier),
    )
    session.commit()
    session.refresh(supplier)
    return supplier


def restore_product(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    product_id: str,
) -> Product:
    product = _get_product_or_error(session, business_id=business_id, product_id=product_id)
    if product.archived_at is None:
        return product
    before = _product_payload(product)
    product.archived_at = None
    write_audit(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="product.restore",
        entity_type="product",
        entity_id=product.id,
        before_data=before,
        after_data=_product_payload(product),
    )
    session.commit()
    session.refresh(product)
    return product


def create_supplier(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    name: str,
    email: str | None,
    phone: str | None,
    lead_time_days: int,
) -> Supplier:
    if lead_time_days < 0:
        raise CatalogError("Lead time must be 0 or greater.")
    supplier = Supplier(
        id=new_id(),
        business_id=business_id,
        name=name.strip(),
        email=email.strip() if email else None,
        phone=phone.strip() if phone else None,
        lead_time_days=lead_time_days,
    )
    session.add(supplier)
    write_audit(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="supplier.create",
        entity_type="supplier",
        entity_id=supplier.id,
        before_data=None,
        after_data=_supplier_payload(supplier),
    )
    session.commit()
    session.refresh(supplier)
    return supplier


def update_supplier(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    supplier_id: str,
    name: str,
    email: str | None,
    phone: str | None,
    lead_time_days: int,
) -> Supplier:
    if lead_time_days < 0:
        raise CatalogError("Lead time must be 0 or greater.")
    supplier = _get_supplier_or_error(session, business_id=business_id, supplier_id=supplier_id)
    before = _supplier_payload(supplier)
    supplier.name = name.strip()
    supplier.email = email.strip() if email else None
    supplier.phone = phone.strip() if phone else None
    supplier.lead_time_days = lead_time_days
    write_audit(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="supplier.update",
        entity_type="supplier",
        entity_id=supplier.id,
        before_data=before,
        after_data=_supplier_payload(supplier),
    )
    session.commit()
    session.refresh(supplier)
    return supplier


def archive_supplier(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    supplier_id: str,
) -> Supplier:
    supplier = _get_supplier_or_error(session, business_id=business_id, supplier_id=supplier_id)
    before = _supplier_payload(supplier)
    supplier.archived_at = utcnow()
    write_audit(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="supplier.archive",
        entity_type="supplier",
        entity_id=supplier.id,
        before_data=before,
        after_data=_supplier_payload(supplier),
    )
    session.commit()
    session.refresh(supplier)
    return supplier


def list_products(
    session: Session,
    *,
    business_id: str,
    search: str | None,
    category_id: str | None,
    page: int,
    page_size: int,
    archived: bool = False,
) -> tuple[list[catalog_repo.ProductListRow], int]:
    if page < 1:
        raise CatalogError("Page must be at least 1.")
    if page_size < 1 or page_size > 100:
        raise CatalogError("Page size must be between 1 and 100.")
    return catalog_repo.list_products(
        session,
        business_id=business_id,
        search=search,
        category_id=category_id,
        page=page,
        page_size=page_size,
        archived=archived,
    )


def create_product(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    sku: str,
    name: str,
    category_id: str | None,
    unit: str,
    cost: Decimal | None,
    price: Decimal | None,
    reorder_point: Decimal | None,
    safety_stock: Decimal | None,
    preferred_supplier_id: str | None,
) -> Product:
    _require_non_negative(cost, "Cost")
    _require_non_negative(price, "Price")
    _require_non_negative(reorder_point, "Reorder point")
    _require_non_negative(safety_stock, "Safety stock")
    if category_id is not None:
        _get_category_or_error(session, business_id=business_id, category_id=category_id)
    if catalog_repo.get_product_by_sku(session, business_id, sku.strip()):
        raise CatalogError("A product with this SKU already exists.", 409)

    product = Product(
        id=new_id(),
        business_id=business_id,
        sku=sku.strip(),
        name=name.strip(),
        category_id=category_id,
        unit=unit.strip() or "each",
        cost=cost,
        price=price,
        reorder_point=reorder_point,
        safety_stock=safety_stock,
    )
    session.add(product)
    session.flush()

    if preferred_supplier_id is not None:
        supplier = _get_supplier_or_error(
            session,
            business_id=business_id,
            supplier_id=preferred_supplier_id,
        )
        unit_cost = cost if cost is not None else Decimal("0")
        _set_preferred_supplier(
            session,
            business_id=business_id,
            product=product,
            supplier_id=preferred_supplier_id,
            unit_cost=unit_cost,
            lead_time_days=supplier.lead_time_days,
        )

    write_audit(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="product.create",
        entity_type="product",
        entity_id=product.id,
        before_data=None,
        after_data=_product_payload(product),
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if "uq_products_business_id_sku" in str(exc.orig):
            raise CatalogError("A product with this SKU already exists.", 409) from exc
        raise
    session.refresh(product)
    return product


def update_product(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    product_id: str,
    sku: str,
    name: str,
    category_id: str | None,
    unit: str,
    cost: Decimal | None,
    price: Decimal | None,
    reorder_point: Decimal | None,
    safety_stock: Decimal | None,
    preferred_supplier_id: str | None,
) -> Product:
    _require_non_negative(cost, "Cost")
    _require_non_negative(price, "Price")
    _require_non_negative(reorder_point, "Reorder point")
    _require_non_negative(safety_stock, "Safety stock")
    product = _get_product_or_error(
        session,
        business_id=business_id,
        product_id=product_id,
        active_only=True,
    )
    if category_id is not None:
        _get_category_or_error(session, business_id=business_id, category_id=category_id)

    before = _product_payload(product)
    next_sku = sku.strip()
    existing = catalog_repo.get_product_by_sku(session, business_id, next_sku)
    if existing is not None and existing.id != product.id:
        raise CatalogError("A product with this SKU already exists.", 409)
    product.sku = next_sku
    product.name = name.strip()
    product.category_id = category_id
    product.unit = unit.strip() or "each"
    product.cost = cost
    product.price = price
    product.reorder_point = reorder_point
    product.safety_stock = safety_stock

    if preferred_supplier_id is None:
        catalog_repo.clear_preferred_supplier(session, business_id, product.id)
    else:
        supplier = _get_supplier_or_error(
            session,
            business_id=business_id,
            supplier_id=preferred_supplier_id,
        )
        unit_cost = cost if cost is not None else Decimal("0")
        _set_preferred_supplier(
            session,
            business_id=business_id,
            product=product,
            supplier_id=preferred_supplier_id,
            unit_cost=unit_cost,
            lead_time_days=supplier.lead_time_days,
        )

    write_audit(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="product.update",
        entity_type="product",
        entity_id=product.id,
        before_data=before,
        after_data=_product_payload(product),
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if "uq_products_business_id_sku" in str(exc.orig):
            raise CatalogError("A product with this SKU already exists.", 409) from exc
        raise
    session.refresh(product)
    return product


def archive_product(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    product_id: str,
) -> Product:
    product = _get_product_or_error(
        session,
        business_id=business_id,
        product_id=product_id,
        active_only=True,
    )
    before = _product_payload(product)
    product.archived_at = utcnow()
    write_audit(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="product.archive",
        entity_type="product",
        entity_id=product.id,
        before_data=before,
        after_data=_product_payload(product),
    )
    session.commit()
    session.refresh(product)
    return product


def list_product_suppliers(
    session: Session,
    *,
    business_id: str,
    product_id: str,
) -> list[ProductSupplier]:
    _get_product_or_error(session, business_id=business_id, product_id=product_id)
    return catalog_repo.list_product_suppliers(session, business_id, product_id)


def create_product_supplier(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    product_id: str,
    supplier_id: str,
    unit_cost: Decimal,
    lead_time_days: int,
    supplier_sku: str | None = None,
    is_preferred: bool = False,
) -> ProductSupplier:
    if unit_cost < 0:
        raise CatalogError("Unit cost must be 0 or greater.")
    if lead_time_days < 0:
        raise CatalogError("Lead time must be 0 or greater.")
    product = _get_product_or_error(
        session,
        business_id=business_id,
        product_id=product_id,
        active_only=True,
    )
    _get_supplier_or_error(session, business_id=business_id, supplier_id=supplier_id)
    if catalog_repo.get_product_supplier_link(
        session,
        business_id,
        product.id,
        supplier_id,
    ):
        raise CatalogError("This supplier is already linked to the product.", 409)

    if is_preferred:
        catalog_repo.clear_preferred_supplier(session, business_id, product.id)

    link = ProductSupplier(
        id=new_id(),
        business_id=business_id,
        product_id=product.id,
        supplier_id=supplier_id,
        supplier_sku=supplier_sku,
        unit_cost=unit_cost,
        lead_time_days=lead_time_days,
        is_preferred=is_preferred,
    )
    session.add(link)
    write_audit(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="product_supplier.create",
        entity_type="product_supplier",
        entity_id=link.id,
        before_data=None,
        after_data=_product_supplier_payload(link),
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise CatalogError("This supplier is already linked to the product.", 409) from exc
    session.refresh(link)
    return link


def update_product_supplier(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    link_id: str,
    unit_cost: Decimal,
    lead_time_days: int,
    supplier_sku: str | None = None,
    is_preferred: bool = False,
) -> ProductSupplier:
    if unit_cost < 0:
        raise CatalogError("Unit cost must be 0 or greater.")
    if lead_time_days < 0:
        raise CatalogError("Lead time must be 0 or greater.")
    link = catalog_repo.get_product_supplier_by_id(session, business_id, link_id)
    if link is None:
        raise CatalogError("Product supplier link not found.", 404)
    before = _product_supplier_payload(link)
    if is_preferred:
        catalog_repo.clear_preferred_supplier(session, business_id, link.product_id)
    link.unit_cost = unit_cost
    link.lead_time_days = lead_time_days
    link.supplier_sku = supplier_sku
    link.is_preferred = is_preferred
    write_audit(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="product_supplier.update",
        entity_type="product_supplier",
        entity_id=link.id,
        before_data=before,
        after_data=_product_supplier_payload(link),
    )
    session.commit()
    session.refresh(link)
    return link


def delete_product_supplier(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    link_id: str,
) -> None:
    link = catalog_repo.get_product_supplier_by_id(session, business_id, link_id)
    if link is None:
        raise CatalogError("Product supplier link not found.", 404)
    before = _product_supplier_payload(link)
    write_audit(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action="product_supplier.delete",
        entity_type="product_supplier",
        entity_id=link.id,
        before_data=before,
        after_data=None,
    )
    session.delete(link)
    session.commit()
