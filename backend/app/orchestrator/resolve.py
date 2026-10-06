from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Product, Supplier
from app.repositories.catalog import get_product_by_sku, list_products, list_suppliers


def resolve_entity_ids(
    session: Session,
    *,
    business_id: str,
    params: dict[str, object],
    history_text: str = "",
) -> dict[str, object]:
    """Turn names from the model into real tenant ids. Never trust a model-supplied id from another tenant."""
    resolved = dict(params)
    supplier_name = str(resolved.get("supplier_name") or "").strip()
    if not resolved.get("supplier_id") and not supplier_name:
        supplier_name = _last_named(history_text, [row.name for row in list_suppliers(session, business_id)])
        if supplier_name:
            resolved["supplier_name"] = supplier_name
    if supplier_name:
        match = _match_supplier(session, business_id, supplier_name)
        if match is not None:
            resolved["supplier_id"] = match.id
            resolved["supplier_name"] = match.name
    elif resolved.get("supplier_id"):
        match = _match_supplier_id(session, business_id, str(resolved["supplier_id"]))
        if match is None:
            resolved.pop("supplier_id", None)
        else:
            resolved["supplier_id"] = match.id

    product_name = str(resolved.get("product_name") or "").strip()
    sku = str(resolved.get("sku") or "").strip()
    if sku:
        product = get_product_by_sku(session, business_id, sku)
        if product is not None:
            resolved["product_id"] = product.id
            resolved["product_name"] = product.name
            resolved["sku"] = product.sku
    elif product_name:
        product = _match_product(session, business_id, product_name)
        if product is not None:
            resolved["product_id"] = product.id
            resolved["product_name"] = product.name
            resolved["sku"] = product.sku
    elif resolved.get("product_id"):
        product = _match_product_id(session, business_id, str(resolved["product_id"]))
        if product is None:
            resolved.pop("product_id", None)
        else:
            resolved["product_id"] = product.id
    return resolved


def _last_named(history_text: str, names: list[str]) -> str:
    blob = history_text.lower()
    last = ""
    last_pos = -1
    for name in names:
        pos = blob.rfind(name.lower())
        if pos > last_pos:
            last_pos = pos
            last = name
    return last


def _match_supplier(session: Session, business_id: str, name: str) -> Supplier | None:
    needle = name.lower()
    for row in list_suppliers(session, business_id, active_only=False):
        if row.name.lower() == needle:
            return row
    matches = [row for row in list_suppliers(session, business_id) if needle in row.name.lower()]
    if len(matches) == 1:
        return matches[0]
    return None


def _match_supplier_id(session: Session, business_id: str, supplier_id: str) -> Supplier | None:
    for row in list_suppliers(session, business_id, active_only=False):
        if row.id == supplier_id:
            return row
    return None


def _match_product(session: Session, business_id: str, name: str) -> Product | None:
    needle = name.lower()
    rows, _total = list_products(
        session,
        business_id=business_id,
        search=name,
        category_id=None,
        page=1,
        page_size=50,
    )
    exact = [row for row in rows if row.name.lower() == needle]
    if len(exact) == 1:
        return session.get(Product, exact[0].id)
    if len(rows) == 1:
        return session.get(Product, rows[0].id)
    return None


def _match_product_id(session: Session, business_id: str, product_id: str) -> Product | None:
    product = session.get(Product, product_id)
    if product is None or product.business_id != business_id:
        return None
    return product
