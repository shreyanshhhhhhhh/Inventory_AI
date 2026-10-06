import type {
  ChatThreadMessage,
  ChatUiState,
  PlanState,
  PlanStep,
  PlanStepStatus,
  TimelineItem,
} from "@/lib/chat/types";

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function asString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

export function durationMs(started: string | null, finished: string | null): number | null {
  if (!started || !finished) return null;
  const ms = new Date(finished).getTime() - new Date(started).getTime();
  return Number.isFinite(ms) && ms >= 0 ? ms : null;
}

export function assistantOf(state: ChatUiState): ChatThreadMessage | null {
  const id = state.activeMessageId;
  if (!id) return null;
  return state.messages.find((item) => item.id === id) ?? null;
}

export function patchAssistant(
  state: ChatUiState,
  patch: Partial<Extract<ChatThreadMessage, { role: "assistant" }>>,
): ChatUiState {
  const current = assistantOf(state);
  if (!current || current.role !== "assistant") return state;
  return {
    ...state,
    messages: state.messages.map((item) =>
      item.id === current.id && item.role === "assistant" ? { ...item, ...patch } : item,
    ),
  };
}

export function timelineFromPlan(plan: PlanState | null): TimelineItem[] {
  if (!plan) return [];
  return plan.steps
    .filter((step) => step.agent !== "guardrail")
    .map((step) => ({
      stepId: step.id,
      agent: step.agent,
      task: step.task,
      status: step.status,
      durationMs: step.durationMs,
      tool: `${step.agent}.${step.task}`,
      error: step.error,
    }));
}

export function parseSteps(raw: unknown): PlanStep[] {
  if (!Array.isArray(raw)) return [];
  const steps: PlanStep[] = [];
  for (const item of raw) {
    if (!isRecord(item) || typeof item.id !== "string") continue;
    const status: PlanStepStatus =
      item.status === "running" ||
      item.status === "completed" ||
      item.status === "failed" ||
      item.status === "skipped"
        ? item.status
        : "pending";
    steps.push({
      id: item.id,
      agent: asString(item.agent) ?? "unknown",
      task: asString(item.task) ?? "unknown",
      depends_on: Array.isArray(item.depends_on)
        ? item.depends_on.filter((value): value is string => typeof value === "string")
        : [],
      is_write: Boolean(item.is_write),
      status,
      error: asString(item.error),
      startedAt: null,
      finishedAt: null,
      durationMs: null,
      progress: null,
      resultType: null,
    });
  }
  return steps;
}

function pickLive(step: PlanStep): Partial<PlanStep> {
  return {
    status: step.status,
    error: step.error,
    startedAt: step.startedAt,
    finishedAt: step.finishedAt,
    durationMs: step.durationMs,
    progress: step.progress,
    resultType: step.resultType,
  };
}

export function mergePlan(
  existing: PlanStep[],
  raw: Record<string, unknown>,
  awaiting: boolean,
): PlanState {
  const incoming = parseSteps(raw.steps);
  const steps = incoming.map((step) => {
    const prev = existing.find((item) => item.id === step.id);
    return prev ? { ...step, ...pickLive(prev) } : step;
  });
  return {
    steps,
    awaitingApproval: awaiting,
    actions: awaiting ? ["run", "edit", "cancel"] : [],
  };
}
