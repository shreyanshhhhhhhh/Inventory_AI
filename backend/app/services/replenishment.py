from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Product, StockMovement
from app.services.forecast import list_forecasts


def reorder_recommendations(
    session: Session,
    *,
    business_id: str,
) -> list[dict[str, object]]:
    on_hand_rows = session.execute(
        select(
            StockMovement.product_id,
            func.coalesce(func.sum(StockMovement.quantity), 0).label("on_hand"),
        )
        .where(StockMovement.business_id == business_id)
        .group_by(StockMovement.product_id)
    ).all()
    on_hand_by_product = {
        row.product_id: Decimal(row.on_hand) for row in on_hand_rows
    }
    forecasts = list_forecasts(session, business_id=business_id)
    forecast_by_product = {
        item["product_id"]: Decimal(str(item["forecast_units"]))
        for item in forecasts["items"]
    }
    products = session.scalars(
        select(Product)
        .where(Product.business_id == business_id, Product.archived_at.is_(None))
        .order_by(Product.name.asc())
    ).all()

    recommendations: list[dict[str, object]] = []
    for product in products:
        on_hand = on_hand_by_product.get(product.id, Decimal("0"))
        forecast_units = forecast_by_product.get(product.id, Decimal("0"))
        reorder_point = product.reorder_point or Decimal("0")
        safety_stock = product.safety_stock or Decimal("0")
        needed = max(reorder_point, forecast_units) + safety_stock
        if on_hand >= needed:
            continue
        recommendations.append(
            {
                "product_id": product.id,
                "sku": product.sku,
                "product_name": product.name,
                "on_hand": on_hand,
                "reorder_point": product.reorder_point,
                "safety_stock": product.safety_stock,
                "forecast_units": forecast_units,
                "recommended_quantity": needed - on_hand,
            }
        )
    return recommendations
