from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CARD_TYPES = (
    "stock_table",
    "forecast_chart",
    "exception_list",
    "po_suggestion",
    "email_draft",
    "explanation",
    "whatif_compare",
    "text",
    "clarification",
    "refusal",
    "plan",
)

CardType = Literal[
    "stock_table",
    "forecast_chart",
    "exception_list",
    "po_suggestion",
    "email_draft",
    "explanation",
    "whatif_compare",
    "text",
    "clarification",
    "refusal",
    "plan",
]

StepStatus = Literal["pending", "running", "completed", "failed", "skipped"]
IntentName = Literal[
    "get_stock",
    "forecast",
    "scan_exceptions",
    "reorder",
    "draft_po",
    "draft_email",
    "explain",
    "whatif",
    "data_quality",
]


class IntentParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: str | None = None
    supplier_name: str | None = None
    product_id: str | None = None
    product_name: str | None = None
    sku: str | None = None
    location_id: str | None = None
    query: str | None = None


class IntentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str
    params: dict[str, Any] = Field(default_factory=dict)


class UnderstandOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intents: list[IntentItem] = Field(default_factory=list)
    confidence: float = 0
    ambiguous: bool = False


class PlanStepModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    agent: str
    task: str
    depends_on: list[str] = Field(default_factory=list)


class ProposedPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[PlanStepModel] = Field(default_factory=list)


class PlanStep:
    def __init__(
        self,
        *,
        id: str,
        agent: str,
        task: str,
        depends_on: list[str],
        is_write: bool,
        intent: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> None:
        self.id = id
        self.agent = agent
        self.task = task
        self.depends_on = list(depends_on)
        self.is_write = is_write
        self.intent = intent
        self.params = dict(params or {})
        self.status: StepStatus = "pending"
        self.error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent": self.agent,
            "task": self.task,
            "depends_on": list(self.depends_on),
            "is_write": self.is_write,
            "intent": self.intent,
            "params": dict(self.params),
            "status": self.status,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> PlanStep:
        step = cls(
            id=str(payload["id"]),
            agent=str(payload["agent"]),
            task=str(payload["task"]),
            depends_on=[str(item) for item in payload.get("depends_on") or []],
            is_write=bool(payload.get("is_write", False)),
            intent=str(payload["intent"]) if payload.get("intent") else None,
            params=dict(payload.get("params") or {}),
        )
        step.status = payload.get("status") or "pending"  # type: ignore[assignment]
        step.error = str(payload["error"]) if payload.get("error") else None
        return step


class Plan:
    def __init__(self, steps: list[PlanStep]) -> None:
        self.steps = steps

    @property
    def has_writes(self) -> bool:
        return any(step.is_write for step in self.steps if step.agent != "guardrail")

    def to_dict(self) -> dict[str, Any]:
        return {"steps": [step.to_dict() for step in self.steps]}

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> Plan:
        raw_steps = (payload or {}).get("steps") or []
        return cls([PlanStep.from_dict(item) for item in raw_steps])

    def by_id(self) -> dict[str, PlanStep]:
        return {step.id: step for step in self.steps}


class TypedResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    agent: str
    task: str
    status: Literal["ok", "failed", "skipped", "not_implemented"]
    card_type: CardType
    data: dict[str, Any] = Field(default_factory=dict)
    message: str = ""

    def to_card(self) -> dict[str, Any]:
        return {
            "type": self.card_type,
            "step_id": self.step_id,
            "agent": self.agent,
            "task": self.task,
            "status": self.status,
            "data": self.data,
            "message": self.message,
        }


class SummaryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
