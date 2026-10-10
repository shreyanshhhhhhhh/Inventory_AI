import csv
import io
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Product, ProductSupplier, Supplier
from app.models.types import new_id
from app.repositories import catalog as catalog_repo
from app.repositories import inventory as inventory_repo
from app.services.audit import log_action
from app.services.catalog import CatalogError, _set_preferred_supplier
from app.services.inventory import InventoryError, post_movement


PRODUCT_HEADERS = [
    "sku",
    "name",
    "category",
    "location",
    "quantity",
    "unit",
    "reorder_point",
    "supplier",
    "unit_cost",
    "lead_time_days",
]

SALES_HEADERS = ["date", "sku", "location", "quantity", "note"]

PRODUCT_SAMPLE_CSV = """sku,name,category,location,quantity,unit,reorder_point,supplier,unit_cost,lead_time_days
NEW-001,Sample Item,Produce,Main location,10,each,5,Green Valley Produce,1.50,2
"""

SALES_SAMPLE_CSV = """date,sku,location,quantity,note
2026-01-15,DEMO-001,Main location,2,Morning rush
"""


class ImportError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, code: str = "bad_request") -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


@dataclass
class RowError:
    row: int
    message: str


@dataclass
class ImportResult:
    imported_count: int = 0
    skipped_count: int = 0
    errors: list[RowError] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "imported_count": self.imported_count,
            "skipped_count": self.skipped_count,
            "error_count": len(self.errors),
            "errors": [{"row": error.row, "message": error.message} for error in self.errors],
            "success": self.success,
        }


def _parse_decimal(value: str, label: str) -> Decimal:
    try:
        return Decimal(value.strip())
    except InvalidOperation as exc:
        raise ValueError(f"{label} must be a number.") from exc


def _parse_csv(text: str) -> tuple[list[str], list[dict[str, str]]]:
    if not text.strip():
        raise ImportError("CSV file is empty.")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ImportError("CSV header row is missing.")
    headers = [header.strip() for header in reader.fieldnames]
    rows: list[dict[str, str]] = []
    for raw in reader:
        rows.append({key.strip(): (value or "").strip() for key, value in raw.items() if key})
    return headers, rows


def _audit_import_create(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    entity_type: str,
    entity_id: str,
    data: dict[str, object],
) -> None:
    log_action(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        action=f"{entity_type}.create",
        entity_type=entity_type,
        entity_id=entity_id,
        before_data=None,
        after_data={"id": entity_id, **data, "source": "csv_import"},
    )


def _get_or_create_category(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    cache: dict[str, Category],
    name: str,
) -> Category:
    key = name.strip().lower()
    if key in cache:
        return cache[key]
    existing = session.scalar(
        select(Category).where(
            Category.business_id == business_id,
            func.lower(Category.name) == key,
        )
    )
    if existing is not None:
        cache[key] = existing
        return existing
    category = Category(id=new_id(), business_id=business_id, name=name.strip())
    session.add(category)
    session.flush()
    _audit_import_create(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        entity_type="category",
        entity_id=category.id,
        data={"name": category.name},
    )
    cache[key] = category
    return category


def _get_or_create_supplier(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    cache: dict[str, Supplier],
    name: str,
    lead_time_days: int,
) -> Supplier:
    key = name.strip().lower()
    if key in cache:
        return cache[key]
    existing = session.scalar(
        select(Supplier).where(
            Supplier.business_id == business_id,
            func.lower(Supplier.name) == key,
            Supplier.archived_at.is_(None),
        )
    )
    if existing is not None:
        cache[key] = existing
        return existing
    supplier = Supplier(
        id=new_id(),
        business_id=business_id,
        name=name.strip(),
        lead_time_days=lead_time_days,
    )
    session.add(supplier)
    session.flush()
    _audit_import_create(
        session,
        business_id=business_id,
        actor_user_id=actor_user_id,
        entity_type="supplier",
        entity_id=supplier.id,
        data={"name": supplier.name, "lead_time_days": lead_time_days},
    )
    cache[key] = supplier
    return supplier


def _resolve_location(session: Session, *, business_id: str, name: str):
    locations = inventory_repo.list_locations(session, business_id)
    normalized = name.strip().lower()
    for location in locations:
        if location.name.lower() == normalized:
            return location
    raise ValueError(f"Location '{name}' was not found.")


def _validate_product_row(row_number: int, row: dict[str, str]) -> RowError | None:
    sku = row.get("sku", "").strip()
    name = row.get("name", "").strip()
    if not sku:
        return RowError(row_number, "sku is required.")
    if not name:
        return RowError(row_number, "name is required.")
    unit_cost = row.get("unit_cost", "").strip()
    supplier = row.get("supplier", "").strip()
    if unit_cost and not supplier:
        return RowError(row_number, "supplier is required when unit_cost is provided.")
    if supplier and not unit_cost:
        return RowError(row_number, "unit_cost is required when supplier is provided.")
    quantity = row.get("quantity", "").strip()
    if quantity:
        try:
            parsed = _parse_decimal(quantity, "quantity")
            if parsed < 0:
                return RowError(row_number, "quantity must be 0 or greater.")
        except ValueError as exc:
            return RowError(row_number, str(exc))
    reorder_point = row.get("reorder_point", "").strip()
    if reorder_point:
        try:
            parsed = _parse_decimal(reorder_point, "reorder_point")
            if parsed < 0:
                return RowError(row_number, "reorder_point must be 0 or greater.")
        except ValueError as exc:
            return RowError(row_number, str(exc))
    if unit_cost:
        try:
            parsed = _parse_decimal(unit_cost, "unit_cost")
            if parsed < 0:
                return RowError(row_number, "unit_cost must be 0 or greater.")
        except ValueError as exc:
            return RowError(row_number, str(exc))
    lead_time = row.get("lead_time_days", "").strip()
    if lead_time:
        try:
            if int(lead_time) < 0:
                return RowError(row_number, "lead_time_days must be 0 or greater.")
        except ValueError:
            return RowError(row_number, "lead_time_days must be an integer.")
    location = row.get("location", "").strip()
    if quantity and not location:
        return RowError(row_number, "location is required when quantity is provided.")
    return None


def _validate_sales_row(
    session: Session,
    *,
    business_id: str,
    row_number: int,
    row: dict[str, str],
) -> RowError | None:
    sku = row.get("sku", "").strip()
    location_name = row.get("location", "").strip()
    quantity_text = row.get("quantity", "").strip()
    date_text = row.get("date", "").strip()
    if not date_text:
        return RowError(row_number, "date is required.")
    if not sku:
        return RowError(row_number, "sku is required.")
    if not location_name:
        return RowError(row_number, "location is required.")
    if not quantity_text:
        return RowError(row_number, "quantity is required.")
    try:
        quantity = _parse_decimal(quantity_text, "quantity")
        if quantity <= 0:
            return RowError(row_number, "quantity must be greater than 0.")
    except ValueError as exc:
        return RowError(row_number, str(exc))
    try:
        datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return RowError(row_number, "date must use YYYY-MM-DD format.")
    product = catalog_repo.get_product_by_sku(session, business_id, sku)
    if product is None or product.archived_at is not None:
        return RowError(row_number, f"Product '{sku}' was not found.")
    try:
        _resolve_location(session, business_id=business_id, name=location_name)
    except ValueError as exc:
        return RowError(row_number, str(exc))
    return None


def validate_products_csv(session: Session, *, business_id: str, csv_text: str) -> ImportResult:
    headers, rows = _parse_csv(csv_text)
    missing = [header for header in PRODUCT_HEADERS if header not in headers]
    if missing:
        raise ImportError(f"Missing required columns: {', '.join(missing)}.")

    result = ImportResult()
    seen_skus: set[str] = set()
    for index, row in enumerate(rows, start=2):
        if not any(value.strip() for value in row.values()):
            continue
        error = _validate_product_row(index, row)
        if error:
            result.errors.append(error)
            continue
        sku = row["sku"].strip()
        if sku.lower() in seen_skus:
            result.errors.append(RowError(index, f"Duplicate sku '{sku}' in file."))
            continue
        seen_skus.add(sku.lower())
        if catalog_repo.get_product_by_sku(session, business_id, sku):
            result.errors.append(RowError(index, f"Product '{sku}' already exists."))
    return result


def import_products_csv(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    csv_text: str,
    skip_errors: bool = False,
) -> ImportResult:
    validation = validate_products_csv(session, business_id=business_id, csv_text=csv_text)
    if validation.errors and not skip_errors:
        return validation

    _, rows = _parse_csv(csv_text)
    bad_rows = {error.row for error in validation.errors}
    category_cache: dict[str, Category] = {}
    supplier_cache: dict[str, Supplier] = {}

    try:
        for index, row in enumerate(rows, start=2):
            if not any(value.strip() for value in row.values()):
                continue
            if index in bad_rows:
                validation.skipped_count += 1
                continue

            sku = row["sku"].strip()
            name = row["name"].strip()
            category_name = row.get("category", "").strip()
            category_id = None
            if category_name:
                category = _get_or_create_category(
                    session,
                    business_id=business_id,
                    actor_user_id=actor_user_id,
                    cache=category_cache,
                    name=category_name,
                )
                category_id = category.id

            unit = row.get("unit", "").strip() or "each"
            reorder_point = (
                _parse_decimal(row["reorder_point"], "reorder_point")
                if row.get("reorder_point", "").strip()
                else None
            )
            cost = (
                _parse_decimal(row["unit_cost"], "unit_cost")
                if row.get("unit_cost", "").strip()
                else None
            )

            product = Product(
                id=new_id(),
                business_id=business_id,
                sku=sku,
                name=name,
                category_id=category_id,
                unit=unit,
                cost=cost,
                price=None,
                reorder_point=reorder_point,
                safety_stock=None,
            )
            session.add(product)
            session.flush()

            supplier_name = row.get("supplier", "").strip()
            if supplier_name:
                lead_time = int(row.get("lead_time_days", "").strip() or "0")
                supplier = _get_or_create_supplier(
                    session,
                    business_id=business_id,
                    actor_user_id=actor_user_id,
                    cache=supplier_cache,
                    name=supplier_name,
                    lead_time_days=lead_time,
                )
                unit_cost = cost if cost is not None else Decimal("0")
                _set_preferred_supplier(
                    session,
                    business_id=business_id,
                    product=product,
                    supplier_id=supplier.id,
                    unit_cost=unit_cost,
                    lead_time_days=lead_time,
                )

            quantity_text = row.get("quantity", "").strip()
            location_name = row.get("location", "").strip()
            if quantity_text and location_name:
                quantity = _parse_decimal(quantity_text, "quantity")
                if quantity > 0:
                    location = _resolve_location(session, business_id=business_id, name=location_name)
                    post_movement(
                        session,
                        business_id=business_id,
                        actor_user_id=actor_user_id,
                        product_id=product.id,
                        location_id=location.id,
                        movement_type="adjustment",
                        quantity=quantity,
                        note="Opening balance",
                        commit=False,
                    )

            _audit_import_create(
                session,
                business_id=business_id,
                actor_user_id=actor_user_id,
                entity_type="product",
                entity_id=product.id,
                data={
                    "sku": sku,
                    "name": name,
                    "cost": str(cost) if cost is not None else None,
                    "reorder_point": str(reorder_point) if reorder_point is not None else None,
                },
            )
            validation.imported_count += 1

        if validation.errors and not skip_errors:
            session.rollback()
            validation.imported_count = 0
            return validation

        session.commit()
        return validation
    except (CatalogError, InventoryError, ValueError) as exc:
        session.rollback()
        raise ImportError(str(exc)) from exc


def validate_sales_csv(session: Session, *, business_id: str, csv_text: str) -> ImportResult:
    headers, rows = _parse_csv(csv_text)
    missing = [header for header in SALES_HEADERS if header not in headers]
    if missing:
        raise ImportError(f"Missing required columns: {', '.join(missing)}.")

    result = ImportResult()
    for index, row in enumerate(rows, start=2):
        if not any(value.strip() for value in row.values()):
            continue
        error = _validate_sales_row(session, business_id=business_id, row_number=index, row=row)
        if error:
            result.errors.append(error)
    return result


def import_sales_csv(
    session: Session,
    *,
    business_id: str,
    actor_user_id: str,
    csv_text: str,
    skip_errors: bool = False,
) -> ImportResult:
    validation = validate_sales_csv(session, business_id=business_id, csv_text=csv_text)
    if validation.errors and not skip_errors:
        return validation

    _, rows = _parse_csv(csv_text)
    bad_rows = {error.row for error in validation.errors}

    parsed_rows: list[tuple[int, dict[str, str], datetime]] = []
    for index, row in enumerate(rows, start=2):
        if not any(value.strip() for value in row.values()):
            continue
        if index in bad_rows:
            validation.skipped_count += 1
            continue
        occurred_at = datetime.strptime(row["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        parsed_rows.append((index, row, occurred_at))

    parsed_rows.sort(key=lambda item: item[2])

    try:
        for index, row, occurred_at in parsed_rows:
            product = catalog_repo.get_product_by_sku(session, business_id, row["sku"].strip())
            if product is None:
                validation.errors.append(RowError(index, f"Product '{row['sku']}' was not found."))
                validation.skipped_count += 1
                continue
            location = _resolve_location(session, business_id=business_id, name=row["location"].strip())
            quantity = _parse_decimal(row["quantity"], "quantity")
            note = row.get("note", "").strip() or None
            try:
                post_movement(
                    session,
                    business_id=business_id,
                    actor_user_id=actor_user_id,
                    product_id=product.id,
                    location_id=location.id,
                    movement_type="sale",
                    quantity=quantity,
                    note=note,
                    occurred_at=occurred_at,
                    commit=False,
                )
            except InventoryError as exc:
                validation.errors.append(RowError(index, exc.message))
                if not skip_errors:
                    session.rollback()
                    validation.imported_count = 0
                    return validation
                validation.skipped_count += 1
                continue
            validation.imported_count += 1

        if validation.errors and not skip_errors:
            session.rollback()
            validation.imported_count = 0
            return validation

        session.commit()
        return validation
    except InventoryError as exc:
        session.rollback()
        raise ImportError(exc.message, status_code=exc.status_code, code=exc.code) from exc
