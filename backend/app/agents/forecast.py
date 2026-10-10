from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.base import BaseAgent
from app.agents.context import AgentContext
from app.agents.errors import AgentError
from app.agents.tools import (
    GetForecastAccuracyOutput,
    GetForecastOutput,
    GetHistoryOutput,
    GetStockOutput,
    RunForecastOutput,
)
from app.core.jsonutil import jsonable
from app.llm.prompts.registry import get_prompt
from app.llm.providers.base import ChatMessage
from app.llm.security import DATA_BLOCK_INSTRUCTIONS, wrap_untrusted
from app.orchestrator.aggregate import numbers_in_text, summary_is_grounded
from app.orchestrator.types import TypedResult


class ForecastInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interpretation: str = Field(max_length=240)


def _param_str(params: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = params.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


class ForecastAgent(BaseAgent):
    name = "forecast"
    description = "Demand forecast eval from sale history. Detection and numbers come from tools."
    allowed_tools = frozenset(
        {"get_stock", "get_forecast", "run_forecast", "get_history", "get_forecast_accuracy"}
    )
    max_tool_calls = 8
    prompt_name = "forecast_interpret"

    def execute(self, task: str, context: AgentContext) -> dict[str, object]:
        del context
        result = self.typed_result(task, {}, step_id=task)
        return result.to_card()

    def typed_result(
        self,
        task: str,
        params: dict[str, Any],
        *,
        step_id: str,
    ) -> TypedResult:
        if task == "get_stock":
            return self._stock_card(params, step_id=step_id)
        if task == "forecast":
            return self._forecast_card(params, step_id=step_id)
        return TypedResult(
            step_id=step_id,
            agent=self.name,
            task=task,
            status="failed",
            card_type="text",
            message=f"Unknown forecast task: {task}",
        )

    def _stock_card(self, params: dict[str, Any], *, step_id: str) -> TypedResult:
        search = _param_str(params, "query", "sku", "product_name")
        location_id = _param_str(params, "location_id")
        output = self.invoke_tool(
            "get_stock",
            {
                "search": search,
                "location_id": location_id,
                "page": 1,
                "page_size": 50,
            },
        )
        assert isinstance(output, GetStockOutput)
        data = jsonable(
            {
                "items": [item.model_dump() for item in output.items],
                "total": output.total,
            }
        )
        if output.total == 0:
            message = "No stock rows match this shop yet."
        else:
            message = f"{output.total} stock rows."
        return TypedResult(
            step_id=step_id,
            agent=self.name,
            task="get_stock",
            status="ok",
            card_type="stock_table",
            data=data if isinstance(data, dict) else {},
            message=message,
        )

    def _forecast_card(self, params: dict[str, Any], *, step_id: str) -> TypedResult:
        product_id = _product_id(params)
        query = _param_str(params, "query", "sku", "product_name")
        if query and query.lower() != "all" and not product_id:
            return TypedResult(
                step_id=step_id,
                agent=self.name,
                task="forecast",
                status="ok",
                card_type="forecast_chart",
                data={"items": [], "points": []},
                message="No matching product in this shop.",
            )
        tool_args = {"product_id": product_id} if product_id else {}
        try:
            history = self.invoke_tool("get_history", tool_args)
            evaluated = self.invoke_tool("run_forecast", tool_args)
            accuracy = self.invoke_tool("get_forecast_accuracy", tool_args)
            forecast = self.invoke_tool("get_forecast", tool_args)
        except AgentError as exc:
            return TypedResult(
                step_id=step_id,
                agent=self.name,
                task="forecast",
                status="failed",
                card_type="forecast_chart",
                message=exc.detail,
            )
        assert isinstance(history, GetHistoryOutput)
        assert isinstance(evaluated, RunForecastOutput)
        assert isinstance(accuracy, GetForecastAccuracyOutput)
        assert isinstance(forecast, GetForecastOutput)
        items = [_merge_item(item.model_dump()) for item in evaluated.items]
        points: list[dict[str, object]] = []
        if len(evaluated.items) == 1:
            points = [
                {"date": point.date, "units": str(point.units)}
                for point in evaluated.items[0].forecast
            ]
        typed = {
            "history_days": evaluated.history_days,
            "horizon_days": evaluated.horizon_days,
            "items": items,
            "points": points,
            "accuracy": [item.model_dump() for item in accuracy.items],
            "insights_method_items": [
                {
                    "product_id": item.product_id,
                    "sku": item.sku,
                    "method": item.method,
                    "forecast_units": item.forecast_units,
                }
                for item in forecast.items
            ],
            "history_skus": [item.sku for item in history.items],
        }
        interpretation = (
            _template_interpretation(typed)
            if not evaluated.items
            else self._interpret(typed)
        )
        data = jsonable(typed)
        return TypedResult(
            step_id=step_id,
            agent=self.name,
            task="forecast",
            status="ok",
            card_type="forecast_chart",
            data=data if isinstance(data, dict) else {},
            message=interpretation,
        )

    def _interpret(self, typed: dict[str, object]) -> str:
        template = _template_interpretation(typed)
        prompt = get_prompt(self.prompt_name)
        try:
            parsed = self.call_llm_structured(
                [
                    ChatMessage(
                        role="system",
                        content=f"{prompt.template}\n{DATA_BLOCK_INSTRUCTIONS}",
                    ),
                    ChatMessage(role="user", content=wrap_untrusted(typed, label="forecast")),
                ],
                ForecastInterpretation,
                prompt_name=self.prompt_name,
            )
        except Exception:
            return template
        text = parsed.interpretation.strip().splitlines()[0].strip()
        if not text:
            return template
        fake_result = TypedResult(
            step_id="forecast",
            agent=self.name,
            task="forecast",
            status="ok",
            card_type="forecast_chart",
            data=typed if isinstance(typed, dict) else {},
            message="",
        )
        if numbers_in_text(text) and not summary_is_grounded(text, {"forecast": fake_result}):
            return template
        return text


def _product_id(params: dict[str, Any]) -> str | None:
    query = _param_str(params, "query")
    if query and query.lower() == "all":
        return None
    return _param_str(params, "product_id")


def _merge_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_id": item["product_id"],
        "sku": item["sku"],
        "product_name": item["product_name"],
        "forecast_units": item["forecast_units"],
        "daily_average": item["daily_average"],
        "horizon_days": item["horizon_days"],
        "trend": item["trend"],
        "chosen_model": item["chosen_model"],
        "backtest_wape": item["backtest_wape"],
        "naive_wape": item["naive_wape"],
        "confidence": item["confidence"],
        "caveats": item["caveats"],
        "history_span_days": item["history_span_days"],
        "history_units": item["history_units"],
    }


def _template_interpretation(typed: dict[str, object]) -> str:
    items = typed.get("items")
    rows = items if isinstance(items, list) else []
    if not rows:
        return "No forecast yet. Add sales history to see demand."
    if len(rows) == 1 and isinstance(rows[0], dict):
        item = rows[0]
        caveats = item.get("caveats") or []
        caveat_text = ""
        if isinstance(caveats, list) and caveats:
            caveat_text = " Caveats: " + ", ".join(str(item) for item in caveats) + "."
        return (
            f"{item.get('sku')}: {item.get('trend')} trend under {item.get('chosen_model')}, "
            f"{item.get('confidence')} confidence.{caveat_text}"
        )
    return f"{len(rows)} SKUs. Trend, model, WAPE, and confidence come from the backtest."


def forecast_agent_handler(
    task: str,
    params: dict[str, Any],
    inputs: dict[str, TypedResult],
    context: AgentContext,
) -> TypedResult:
    del inputs
    agent = ForecastAgent()
    agent.attach(context)
    return agent.typed_result(task, params, step_id=str(params.get("_step_id") or task))
