from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.agents.context import AgentContext
from app.agents.errors import AgentError, ToolNotAllowedError, ToolRoleError
from app.core.jsonutil import jsonable
from app.models import AgentStep
from app.models.types import new_id
from app.services import agent_suggestions as suggestion_service
from app.services import replenishment as replenishment_service
from app.services import supplier_reliability as reliability_service
from app.services.dashboard import get_needs_attention
from app.services.forecast import get_forecast, list_forecasts
from app.services.inventory import get_stock_levels


class ToolInputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class ToolCallResult:
    output: BaseModel
    step_id: str


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    read: bool
    required_role: str | None
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable[[AgentContext, BaseModel], BaseModel]


class EmptyInput(ToolInputModel):
    pass


class GetStockInput(ToolInputModel):
    search: str | None = None
    location_id: str | None = None
    low_only: bool = False
    page: int = 1
    page_size: int = 25


class StockItem(BaseModel):
    product_id: str
    location_id: str
    sku: str
    product_name: str
    location_name: str
    on_hand: Decimal
    reorder_point: Decimal | None
    status: str


class GetStockOutput(BaseModel):
    items: list[StockItem]
    total: int


class GetForecastInput(ToolInputModel):
    product_id: str | None = None


class ForecastItem(BaseModel):
    product_id: str
    sku: str
    product_name: str
    history_units: Decimal
    forecast_units: Decimal
    daily_average: Decimal
    method: str


class GetForecastOutput(BaseModel):
    history_days: int
    horizon_days: int
    items: list[ForecastItem]


class LowStockItem(BaseModel):
    product_id: str
    location_id: str
    sku: str
    product_name: str
    location_name: str
    on_hand: Decimal
    reorder_point: Decimal | None
    status: str


class ListLowStockOutput(BaseModel):
    items: list[LowStockItem]


class ReorderItem(BaseModel):
    product_id: str
    sku: str
    product_name: str
    on_hand: Decimal
    reorder_point: Decimal | None
    safety_stock: Decimal | None
    forecast_units: Decimal
    recommended_quantity: Decimal


class ReorderOutput(BaseModel):
    items: list[ReorderItem]


class SupplierReliabilityInput(ToolInputModel):
    supplier_id: str | None = None


class SupplierReliabilityItem(BaseModel):
    supplier_id: str
    supplier_name: str
    lead_time_days: int
    purchase_order_count: int
    open_count: int
    overdue_count: int
    received_count: int
    reliability_score: float


class SupplierReliabilityOutput(BaseModel):
    items: list[SupplierReliabilityItem]


class GenericSuggestionInput(ToolInputModel):
    title: str
    summary: str
    extra: dict[str, Any] | None = None


class DraftPoLine(ToolInputModel):
    product_id: str
    quantity: Decimal
    unit_cost: Decimal | None = None


class DraftPoInput(ToolInputModel):
    supplier_id: str
    location_id: str | None = None
    notes: str | None = None
    lines: list[DraftPoLine] = Field(min_length=1)


class DraftEmailInput(ToolInputModel):
    to_email: str
    subject: str
    body: str


class SuggestionOutput(BaseModel):
    id: str
    suggestion_type: str
    status: str
    payload: dict[str, Any]


def _handle_get_stock(ctx: AgentContext, payload: BaseModel) -> GetStockOutput:
    data = GetStockInput.model_validate(payload.model_dump())
    items, total = get_stock_levels(
        ctx.session,
        business_id=ctx.business_id,
        search=data.search,
        location_id=data.location_id,
        low_only=data.low_only,
        page=data.page,
        page_size=data.page_size,
    )
    return GetStockOutput(items=[StockItem.model_validate(item) for item in items], total=total)


def _handle_get_forecast(ctx: AgentContext, payload: BaseModel) -> GetForecastOutput:
    data = GetForecastInput.model_validate(payload.model_dump())
    if data.product_id:
        raw = get_forecast(ctx.session, business_id=ctx.business_id, product_id=data.product_id)
        item = ForecastItem(
            product_id=str(raw["product_id"]),
            sku=str(raw["sku"]),
            product_name=str(raw["product_name"]),
            history_units=Decimal(str(raw["history_units"])),
            forecast_units=Decimal(str(raw["forecast_units"])),
            daily_average=Decimal(str(raw["daily_average"])),
            method=str(raw["method"]),
        )
        return GetForecastOutput(
            history_days=int(raw["history_days"]),
            horizon_days=int(raw["horizon_days"]),
            items=[item],
        )
    raw = list_forecasts(ctx.session, business_id=ctx.business_id)
    items = [
        ForecastItem(
            product_id=str(item["product_id"]),
            sku=str(item["sku"]),
            product_name=str(item["product_name"]),
            history_units=Decimal(str(item["history_units"])),
            forecast_units=Decimal(str(item["forecast_units"])),
            daily_average=Decimal(str(item["daily_average"])),
            method=str(item["method"]),
        )
        for item in raw["items"]
    ]
    return GetForecastOutput(
        history_days=int(raw["history_days"]),
        horizon_days=int(raw["horizon_days"]),
        items=items,
    )


def _handle_list_low_stock(ctx: AgentContext, payload: BaseModel) -> ListLowStockOutput:
    del payload
    items = get_needs_attention(ctx.session, business_id=ctx.business_id)
    return ListLowStockOutput(items=[LowStockItem.model_validate(item) for item in items])


def _handle_reorder(ctx: AgentContext, payload: BaseModel) -> ReorderOutput:
    del payload
    items = replenishment_service.reorder_recommendations(
        ctx.session,
        business_id=ctx.business_id,
    )
    return ReorderOutput(items=[ReorderItem.model_validate(item) for item in items])


def _handle_reliability(ctx: AgentContext, payload: BaseModel) -> SupplierReliabilityOutput:
    data = SupplierReliabilityInput.model_validate(payload.model_dump())
    items = reliability_service.get_supplier_reliability(
        ctx.session,
        business_id=ctx.business_id,
        supplier_id=data.supplier_id,
    )
    return SupplierReliabilityOutput(
        items=[SupplierReliabilityItem.model_validate(item) for item in items]
    )


def _handle_create_suggestion(ctx: AgentContext, payload: BaseModel) -> SuggestionOutput:
    data = GenericSuggestionInput.model_validate(payload.model_dump())
    body: dict[str, object] = {"title": data.title, "summary": data.summary}
    if data.extra:
        body["extra"] = data.extra
    row = suggestion_service.create_suggestion(
        ctx.session,
        business_id=ctx.business_id,
        actor_user_id=ctx.user_id,
        run_id=ctx.run_id,
        suggestion_type="generic",
        payload=body,
    )
    return SuggestionOutput.model_validate(row)


def _handle_draft_po(ctx: AgentContext, payload: BaseModel) -> SuggestionOutput:
    data = DraftPoInput.model_validate(payload.model_dump())
    row = suggestion_service.create_suggestion(
        ctx.session,
        business_id=ctx.business_id,
        actor_user_id=ctx.user_id,
        run_id=ctx.run_id,
        suggestion_type="draft_po",
        payload=data.model_dump(),
    )
    return SuggestionOutput.model_validate(row)


def _handle_draft_email(ctx: AgentContext, payload: BaseModel) -> SuggestionOutput:
    data = DraftEmailInput.model_validate(payload.model_dump())
    row = suggestion_service.create_suggestion(
        ctx.session,
        business_id=ctx.business_id,
        actor_user_id=ctx.user_id,
        run_id=ctx.run_id,
        suggestion_type="draft_email",
        payload=data.model_dump(),
    )
    return SuggestionOutput.model_validate(row)


TOOLS: dict[str, ToolSpec] = {
    "get_stock": ToolSpec(
        name="get_stock",
        description="On-hand stock by product and location.",
        read=True,
        required_role=None,
        input_model=GetStockInput,
        output_model=GetStockOutput,
        handler=_handle_get_stock,
    ),
    "get_forecast": ToolSpec(
        name="get_forecast",
        description="14-day demand forecast from sale history. Optional product_id.",
        read=True,
        required_role=None,
        input_model=GetForecastInput,
        output_model=GetForecastOutput,
        handler=_handle_get_forecast,
    ),
    "list_low_stock": ToolSpec(
        name="list_low_stock",
        description="SKUs at or below their reorder point.",
        read=True,
        required_role=None,
        input_model=EmptyInput,
        output_model=ListLowStockOutput,
        handler=_handle_list_low_stock,
    ),
    "reorder_recommendations": ToolSpec(
        name="reorder_recommendations",
        description="Deterministic reorder quantities from on-hand, reorder point, and forecast.",
        read=True,
        required_role=None,
        input_model=EmptyInput,
        output_model=ReorderOutput,
        handler=_handle_reorder,
    ),
    "get_supplier_reliability": ToolSpec(
        name="get_supplier_reliability",
        description="Heuristic supplier reliability from purchase-order history and lead time.",
        read=True,
        required_role=None,
        input_model=SupplierReliabilityInput,
        output_model=SupplierReliabilityOutput,
        handler=_handle_reliability,
    ),
    "create_suggestion": ToolSpec(
        name="create_suggestion",
        description="Store a generic agent suggestion. Does not change stock or orders.",
        read=False,
        required_role="owner",
        input_model=GenericSuggestionInput,
        output_model=SuggestionOutput,
        handler=_handle_create_suggestion,
    ),
    "create_draft_po_suggestion": ToolSpec(
        name="create_draft_po_suggestion",
        description="Store a draft purchase-order suggestion. Does not create a purchase order.",
        read=False,
        required_role="owner",
        input_model=DraftPoInput,
        output_model=SuggestionOutput,
        handler=_handle_draft_po,
    ),
    "draft_email": ToolSpec(
        name="draft_email",
        description="Store a supplier email draft. Does not send email.",
        read=False,
        required_role="owner",
        input_model=DraftEmailInput,
        output_model=SuggestionOutput,
        handler=_handle_draft_email,
    ),
}


def get_tool(name: str) -> ToolSpec:
    spec = TOOLS.get(name)
    if spec is None:
        raise ToolNotAllowedError(name)
    return spec


def invoke_tool(
    session: Session,
    *,
    context: AgentContext,
    tool_name: str,
    arguments: dict[str, Any] | BaseModel,
    allowlist: frozenset[str],
) -> ToolCallResult:
    if tool_name not in allowlist:
        raise ToolNotAllowedError(tool_name)
    if context.run_id is None:
        raise AgentError("Tools require an agent run.", code="missing_run")
    spec = get_tool(tool_name)
    if spec.required_role is not None and context.role != spec.required_role:
        raise ToolRoleError(tool_name)
    payload = (
        arguments
        if isinstance(arguments, spec.input_model)
        else spec.input_model.model_validate(arguments)
    )
    started = time.perf_counter()
    output = spec.handler(context, payload)
    duration_ms = int((time.perf_counter() - started) * 1000)
    step = AgentStep(
        id=new_id(),
        run_id=context.run_id,
        business_id=context.business_id,
        step_kind="tool",
        tool_name=spec.name,
        input_data=jsonable(payload),
        output_data=jsonable(output),
        duration_ms=duration_ms,
    )
    session.add(step)
    session.flush()
    return ToolCallResult(output=output, step_id=step.id)
