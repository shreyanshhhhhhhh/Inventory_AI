import {
  asString,
  assistantOf,
  durationMs,
  isRecord,
  mergePlan,
  patchAssistant,
  timelineFromPlan,
} from "@/lib/chat/plan-state";
import type {
  AssistantRunStatus,
  ChatSseEvent,
  ChatUiState,
  OrchestratorCard,
  OrchestratorCardType,
  PlanState,
  PlanStep,
} from "@/lib/chat/types";

function eventKeyMatch(left: ChatSseEvent, right: ChatSseEvent): boolean {
  return (
    left.type === right.type &&
    left.ts === right.ts &&
    left.run_id === right.run_id &&
    JSON.stringify(left.payload) === JSON.stringify(right.payload)
  );
}

export function applyEvent(state: ChatUiState, event: ChatSseEvent): ChatUiState {
  const current = assistantOf(state);
  if (!current || current.role !== "assistant") return state;
  if (current.events.some((item) => eventKeyMatch(item, event))) return state;
  const withEvent: ChatUiState = patchAssistant(state, {
    events: [...current.events, event],
    connectionLost: false,
  });
  return applyEventBody(withEvent, event);
}

function applyEventBody(state: ChatUiState, event: ChatSseEvent): ChatUiState {
  switch (event.type) {
    case "thinking":
      return patchAssistant(state, {
        thinking: asString(event.payload.message) ?? "Thinking...",
        status: "thinking",
      });
    case "plan":
      return patchPlan(state, event.payload, false);
    case "awaiting_approval":
      return patchPlan(
        state,
        isRecord(event.payload.plan) ? event.payload.plan : event.payload,
        true,
      );
    case "step_started":
      return patchStep(
        state,
        asString(event.payload.step_id),
        {
          status: "running",
          startedAt: event.ts,
          agent: asString(event.payload.agent) ?? undefined,
          task: asString(event.payload.task) ?? undefined,
        },
        "running",
      );
    case "step_progress":
      return patchStep(
        state,
        asString(event.payload.step_id),
        { progress: asString(event.payload.message) ?? undefined },
        "running",
      );
    case "step_done": {
      const skipped = event.payload.status === "skipped";
      return patchStep(
        state,
        asString(event.payload.step_id),
        {
          status: skipped ? "skipped" : "completed",
          finishedAt: event.ts,
          resultType: asString(event.payload.result_type),
        },
        "running",
      );
    }
    case "step_failed":
      return patchStep(
        state,
        asString(event.payload.step_id),
        {
          status: "failed",
          finishedAt: event.ts,
          error: asString(event.payload.error) ?? "Step failed.",
        },
        "running",
      );
    case "token":
      return appendToken(state, asString(event.payload.text) ?? "");
    case "card":
      return appendCard(state, event);
    case "done":
      return finish(state, "done", asString(event.payload.summary));
    case "cancelled":
      return finish(state, "cancelled", "The run was cancelled.");
    case "error":
      return finish(state, "error", asString(event.payload.message) ?? "Something went wrong.");
    default:
      return state;
  }
}

function patchPlan(
  state: ChatUiState,
  raw: Record<string, unknown>,
  awaiting: boolean,
): ChatUiState {
  const current = assistantOf(state);
  if (!current || current.role !== "assistant") return state;
  const plan = mergePlan(current.plan?.steps ?? [], raw, awaiting);
  return patchAssistant(state, {
    thinking: null,
    plan,
    timeline: timelineFromPlan(plan),
    status: awaiting ? "awaiting_approval" : "planning",
  });
}

function patchStep(
  state: ChatUiState,
  stepId: string | null,
  patch: Partial<PlanStep> & { agent?: string | null; task?: string | null },
  status: AssistantRunStatus,
): ChatUiState {
  const current = assistantOf(state);
  if (!current || current.role !== "assistant" || !stepId) return state;
  const plan = current.plan ?? { steps: [], awaitingApproval: false, actions: [] };
  let steps = plan.steps;
  if (!steps.some((item) => item.id === stepId)) {
    steps = [
      ...steps,
      {
        id: stepId,
        agent: patch.agent ?? "unknown",
        task: patch.task ?? "unknown",
        depends_on: [],
        is_write: false,
        status: "pending",
        error: null,
        startedAt: null,
        finishedAt: null,
        durationMs: null,
        progress: null,
        resultType: null,
      },
    ];
  }
  steps = steps.map((step) => {
    if (step.id !== stepId) return step;
    const startedAt = patch.startedAt ?? step.startedAt;
    const finishedAt = patch.finishedAt ?? step.finishedAt;
    return {
      ...step,
      ...patch,
      agent: patch.agent ?? step.agent,
      task: patch.task ?? step.task,
      startedAt,
      finishedAt,
      durationMs: durationMs(startedAt, finishedAt),
    };
  });
  const next: PlanState = { ...plan, steps, awaitingApproval: false, actions: [] };
  return patchAssistant(state, {
    thinking: null,
    plan: next,
    timeline: timelineFromPlan(next),
    status,
  });
}

function suggestionStatusFor(
  type: OrchestratorCardType,
  data: Record<string, unknown>,
): "pending" | "approved" | "rejected" | null {
  if (type !== "po_suggestion" && type !== "email_draft") return null;
  const explicit = asString(data.suggestion_status);
  if (explicit === "approved" || explicit === "rejected") return explicit;
  return "pending";
}

function appendToken(state: ChatUiState, text: string): ChatUiState {
  const current = assistantOf(state);
  if (!current || current.role !== "assistant" || !text) return state;
  return patchAssistant(state, {
    thinking: null,
    text: `${current.text}${text}`,
    streaming: true,
    status: "streaming",
  });
}

function cardType(value: unknown): OrchestratorCardType | null {
  const allowed: OrchestratorCardType[] = [
    "stock_table",
    "forecast_chart",
    "exception_list",
    "po_suggestion",
    "email_draft",
    "text",
    "clarification",
    "refusal",
    "plan",
  ];
  return typeof value === "string" && allowed.includes(value as OrchestratorCardType)
    ? (value as OrchestratorCardType)
    : null;
}

function appendCard(state: ChatUiState, event: ChatSseEvent): ChatUiState {
  const current = assistantOf(state);
  if (!current || current.role !== "assistant") return state;
  const raw = isRecord(event.payload.card) ? event.payload.card : event.payload;
  const type = cardType(raw.type);
  if (!type) return state;
  const data: Record<string, unknown> = isRecord(raw.data) ? { ...raw.data } : {};
  for (const key of ["options", "supported_commands", "items", "lines"] as const) {
    if (key in raw && data[key] === undefined) {
      data[key] = raw[key];
    }
  }
  const card: OrchestratorCard = {
    id: `${event.run_id}:${current.cards.length}:${type}`,
    type,
    stepId: asString(raw.step_id),
    agent: asString(raw.agent),
    task: asString(raw.task),
    status: asString(raw.status),
    message: asString(raw.message) ?? "",
    data,
    suggestionStatus: suggestionStatusFor(type, data),
  };
  return patchAssistant(state, {
    thinking: null,
    cards: [...current.cards, card],
  });
}

function finish(
  state: ChatUiState,
  status: Extract<AssistantRunStatus, "done" | "error" | "cancelled">,
  summary: string | null,
): ChatUiState {
  const current = assistantOf(state);
  if (!current || current.role !== "assistant") return state;
  const text = current.text.trim() ? current.text : (summary ?? current.text);
  return {
    ...patchAssistant(state, {
      thinking: null,
      streaming: false,
      status,
      text,
      error: status === "error" ? summary : null,
      plan: current.plan ? { ...current.plan, awaitingApproval: false, actions: [] } : current.plan,
    }),
    sending: false,
    activeRunId: null,
  };
}
