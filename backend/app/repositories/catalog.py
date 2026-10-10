from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Category, Product, ProductSupplier, Supplier


@dataclass(frozen=True)
class ProductListRow:
    id: str
    sku: str
    name: str
    category_id: str | None
    category_name: str | None
    unit: str
    cost: Decimal | None
    price: Decimal | None
    reorder_point: Decimal | None
    safety_stock: Decimal | None
    preferred_supplier_id: str | None
    preferred_supplier_name: str | None
    is_active: bool


def get_category(session: Session, business_id: str, category_id: str) -> Category | None:
    return session.scalar(
        select(Category).where(
            Category.business_id == business_id,
            Category.id == category_id,
        )
    )


def list_categories(session: Session, business_id: str) -> list[Category]:
    return list(
        session.scalars(
            select(Category)
            .where(Category.business_id == business_id)
            .order_by(Category.name.asc())
        )
    )


def get_supplier(session: Session, business_id: str, supplier_id: str) -> Supplier | None:
    return session.scalar(
        select(Supplier).where(
            Supplier.business_id == business_id,
            Supplier.id == supplier_id,
        )
    )


def list_suppliers(
    session: Session,
    business_id: str,
    *,
    active_only: bool = True,
) -> list[Supplier]:
    query = select(Supplier).where(Supplier.business_id == business_id)
    if active_only:
        query = query.where(Supplier.archived_at.is_(None))
    return list(session.scalars(query.order_by(Supplier.name.asc())))


def get_product(session: Session, business_id: str, product_id: str) -> Product | None:
    return session.scalar(
        select(Product).where(
            Product.business_id == business_id,
            Product.id == product_id,
        )
    )


def get_product_by_sku(session: Session, business_id: str, sku: str) -> Product | None:
    return session.scalar(
        select(Product).where(
            Product.business_id == business_id,
            Product.sku == sku,
        )
    )


def get_product_row(
    session: Session,
    business_id: str,
    product_id: str,
) -> ProductListRow | None:
    row = session.execute(
        select(
            Product.id,
            Product.sku,
            Product.name,
            Product.category_id,
            Category.name,
            Product.unit,
            Product.cost,
            Product.price,
            Product.reorder_point,
            Product.safety_stock,
            ProductSupplier.supplier_id,
            Supplier.name,
            Product.archived_at,
        )
        .outerjoin(Category, Category.id == Product.category_id)
        .outerjoin(
            ProductSupplier,
            (ProductSupplier.product_id == Product.id)
            & (ProductSupplier.business_id == business_id)
            & (ProductSupplier.is_preferred.is_(True)),
        )
        .outerjoin(Supplier, Supplier.id == ProductSupplier.supplier_id)
        .where(
            Product.business_id == business_id,
            Product.id == product_id,
        )
    ).first()
    if row is None:
        return None
    return ProductListRow(
        id=row[0],
        sku=row[1],
        name=row[2],
        category_id=row[3],
        category_name=row[4],
        unit=row[5],
        cost=row[6],
        price=row[7],
        reorder_point=row[8],
        safety_stock=row[9],
        preferred_supplier_id=row[10],
        preferred_supplier_name=row[11],
        is_active=row[12] is None,
    )


def list_products(
    session: Session,
    *,
    business_id: str,
    search: str | None,
    category_id: str | None,
    page: int,
    page_size: int,
    archived: bool = False,
) -> tuple[list[ProductListRow], int]:
    filters = [
        Product.business_id == business_id,
        Product.archived_at.is_not(None) if archived else Product.archived_at.is_(None),
    ]
    if category_id is not None:
        filters.append(Product.category_id == category_id)
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))

    total = session.scalar(select(func.count()).select_from(Product).where(*filters)) or 0

    rows = session.execute(
        select(
            Product.id,
            Product.sku,
            Product.name,
            Product.category_id,
            Category.name,
            Product.unit,
            Product.cost,
            Product.price,
            Product.reorder_point,
            Product.safety_stock,
            ProductSupplier.supplier_id,
            Supplier.name,
            Product.archived_at,
        )
        .outerjoin(Category, Category.id == Product.category_id)
        .outerjoin(
            ProductSupplier,
            (ProductSupplier.product_id == Product.id)
            & (ProductSupplier.business_id == business_id)
            & (ProductSupplier.is_preferred.is_(True)),
        )
        .outerjoin(Supplier, Supplier.id == ProductSupplier.supplier_id)
        .where(*filters)
        .order_by(Product.name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        ProductListRow(
            id=row[0],
            sku=row[1],
            name=row[2],
            category_id=row[3],
            category_name=row[4],
            unit=row[5],
            cost=row[6],
            price=row[7],
            reorder_point=row[8],
            safety_stock=row[9],
            preferred_supplier_id=row[10],
            preferred_supplier_name=row[11],
            is_active=row[12] is None,
        )
        for row in rows
    ]
    return items, int(total)


def get_product_supplier_link(
    session: Session,
    business_id: str,
    product_id: str,
    supplier_id: str,
) -> ProductSupplier | None:
    return session.scalar(
        select(ProductSupplier).where(
            ProductSupplier.business_id == business_id,
            ProductSupplier.product_id == product_id,
            ProductSupplier.supplier_id == supplier_id,
        )
    )


def get_product_supplier_by_id(
    session: Session,
    business_id: str,
    link_id: str,
) -> ProductSupplier | None:
    return session.scalar(
        select(ProductSupplier).where(
            ProductSupplier.business_id == business_id,
            ProductSupplier.id == link_id,
        )
    )


def list_product_suppliers(
    session: Session,
    business_id: str,
    product_id: str,
) -> list[ProductSupplier]:
    return list(
        session.scalars(
            select(ProductSupplier)
            .where(
                ProductSupplier.business_id == business_id,
                ProductSupplier.product_id == product_id,
            )
            .order_by(ProductSupplier.is_preferred.desc(), ProductSupplier.created_at.asc())
        )
    )


def clear_preferred_supplier(
    session: Session,
    business_id: str,
    product_id: str,
) -> None:
    links = session.scalars(
        select(ProductSupplier).where(
            ProductSupplier.business_id == business_id,
            ProductSupplier.product_id == product_id,
            ProductSupplier.is_preferred.is_(True),
        )
    )
    for link in links:
        link.is_preferred = False
