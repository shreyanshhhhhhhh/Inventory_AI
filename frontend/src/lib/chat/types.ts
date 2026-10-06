export const CHAT_EVENT_TYPES = [
  "thinking",
  "plan",
  "step_started",
  "step_progress",
  "step_done",
  "step_failed",
  "token",
  "card",
  "awaiting_approval",
  "done",
  "error",
  "cancelled",
] as const;

export type ChatEventType = (typeof CHAT_EVENT_TYPES)[number];

export type PlanStepStatus = "pending" | "running" | "completed" | "failed" | "skipped";

export type PlanStep = {
  id: string;
  agent: string;
  task: string;
  depends_on: string[];
  is_write: boolean;
  status: PlanStepStatus;
  error: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  durationMs: number | null;
  progress: string | null;
  resultType: string | null;
};

export type PlanState = {
  steps: PlanStep[];
  awaitingApproval: boolean;
  actions: Array<"run" | "edit" | "cancel">;
};

export type OrchestratorCardType =
  | "stock_table"
  | "forecast_chart"
  | "exception_list"
  | "po_suggestion"
  | "email_draft"
  | "text"
  | "clarification"
  | "refusal"
  | "plan";

export type OrchestratorCard = {
  id: string;
  type: OrchestratorCardType;
  stepId: string | null;
  agent: string | null;
  task: string | null;
  status: string | null;
  message: string;
  data: Record<string, unknown>;
  suggestionStatus: "pending" | "approved" | "rejected" | null;
};

export type TimelineItem = {
  stepId: string;
  agent: string;
  task: string;
  status: PlanStepStatus;
  durationMs: number | null;
  tool: string;
  error: string | null;
};

export type AssistantRunStatus =
  | "thinking"
  | "planning"
  | "awaiting_approval"
  | "running"
  | "streaming"
  | "done"
  | "error"
  | "cancelled";

export type ChatThreadMessage =
  | {
      id: string;
      role: "user";
      text: string;
      createdAt: string;
    }
  | {
      id: string;
      role: "assistant";
      runId: string | null;
      text: string;
      thinking: string | null;
      streaming: boolean;
      status: AssistantRunStatus;
      plan: PlanState | null;
      cards: OrchestratorCard[];
      timeline: TimelineItem[];
      error: string | null;
      connectionLost: boolean;
      events: ChatSseEvent[];
      createdAt: string;
    };

export type ChatUiState = {
  messages: ChatThreadMessage[];
  activeRunId: string | null;
  activeMessageId: string | null;
  sending: boolean;
};

export type ChatSseEvent = {
  type: ChatEventType;
  run_id: string;
  ts: string;
  payload: Record<string, unknown>;
};

export type ChatRunResponse = {
  id: string;
  status: string;
};

export type ChatRunDetail = {
  id: string;
  status: string;
  input_text: string | null;
  plan: Record<string, unknown> | null;
  events: unknown[];
};
