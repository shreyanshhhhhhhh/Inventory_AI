import { describe, expect, it } from "vitest";

import { chatReducer, initialChatState, type ChatAction } from "@/lib/chat/reducer";
import type { ChatSseEvent, ChatUiState } from "@/lib/chat/types";

function ev(
  type: ChatSseEvent["type"],
  payload: Record<string, unknown> = {},
  ts = "2026-10-06T12:00:00.000Z",
): ChatSseEvent {
  return { type, run_id: "run-1", ts, payload };
}

function startThread(): ChatUiState {
  let state = chatReducer(initialChatState, {
    type: "user_sent",
    messageId: "u1",
    text: "/forecast",
    createdAt: "2026-10-06T12:00:00.000Z",
  });
  state = chatReducer(state, {
    type: "assistant_placeholder",
    messageId: "a1",
    createdAt: "2026-10-06T12:00:00.000Z",
  });
  return chatReducer(state, { type: "run_started", runId: "run-1" });
}

function apply(state: ChatUiState, events: ChatSseEvent[]): ChatUiState {
  return events.reduce<ChatUiState>(
    (next, event) => chatReducer(next, { type: "event", event } satisfies ChatAction),
    state,
  );
}

describe("chat event reducer", () => {
  it("shows thinking immediately and never leaves a blank assistant bubble", () => {
    const state = startThread();
    const assistant = state.messages[1];
    expect(assistant.role).toBe("assistant");
    if (assistant.role !== "assistant") return;
    expect(assistant.thinking).toBe("Thinking...");
    expect(assistant.text).toBe("");
    expect(assistant.status).toBe("thinking");
  });

  it("replaces thinking with a plan checklist", () => {
    const state = apply(startThread(), [
      ev("thinking", { message: "Building a plan." }),
      ev("plan", {
        steps: [
          { id: "s1", agent: "forecast", task: "forecast", depends_on: [], is_write: false },
        ],
      }),
    ]);
    const assistant = state.messages[1];
    if (assistant.role !== "assistant") throw new Error("expected assistant");
    expect(assistant.thinking).toBeNull();
    expect(assistant.plan?.steps[0]?.agent).toBe("forecast");
    expect(assistant.plan?.steps[0]?.status).toBe("pending");
    expect(assistant.status).toBe("planning");
  });

  it("streams tokens onto the summary", () => {
    const state = apply(startThread(), [
      ev("token", { text: "Hello" }, "t1"),
      ev("token", { text: " world" }, "t2"),
    ]);
    const assistant = state.messages[1];
    if (assistant.role !== "assistant") throw new Error("expected assistant");
    expect(assistant.text).toBe("Hello world");
    expect(assistant.streaming).toBe(true);
  });

  it("tracks step lifecycle including skipped dependents", () => {
    let state = apply(startThread(), [
      ev("plan", {
        steps: [
          { id: "s1", agent: "exception_monitor", task: "scan", depends_on: [], is_write: false },
          { id: "s2", agent: "supplier_comm", task: "draft_emails", depends_on: ["s1"], is_write: true },
        ],
      }),
      ev("step_started", { step_id: "s1", agent: "exception_monitor", task: "scan" }, "t1"),
      ev("step_failed", { step_id: "s1", error: "boom" }, "t2"),
      ev("step_done", { step_id: "s2", status: "skipped" }, "t3"),
    ]);
    const assistant = state.messages[1];
    if (assistant.role !== "assistant") throw new Error("expected assistant");
    expect(assistant.plan?.steps.find((s) => s.id === "s1")?.status).toBe("failed");
    expect(assistant.plan?.steps.find((s) => s.id === "s2")?.status).toBe("skipped");
    expect(assistant.timeline[0]?.tool).toBe("exception_monitor.scan");
  });

  it("marks write plans as awaiting approval", () => {
    const state = apply(startThread(), [
      ev("awaiting_approval", {
        plan: {
          steps: [
            { id: "s1", agent: "supplier_comm", task: "draft_emails", depends_on: [], is_write: true },
          ],
        },
        actions: ["run", "edit", "cancel"],
      }),
    ]);
    const assistant = state.messages[1];
    if (assistant.role !== "assistant") throw new Error("expected assistant");
    expect(assistant.status).toBe("awaiting_approval");
    expect(assistant.plan?.awaitingApproval).toBe(true);
    expect(assistant.plan?.actions).toContain("run");
  });

  it("ignores duplicate events on reconnect replay", () => {
    const token = ev("token", { text: "Hi" }, "same");
    const once = apply(startThread(), [token]);
    const twice = apply(once, [token]);
    const assistant = twice.messages[1];
    if (assistant.role !== "assistant") throw new Error("expected assistant");
    expect(assistant.text).toBe("Hi");
    expect(assistant.events).toHaveLength(1);
  });

  it("surfaces clarification cards and terminal error/cancel", () => {
    const clarified = apply(startThread(), [
      ev("card", {
        card: {
          type: "clarification",
          message: "Pick one",
          data: {},
          options: [{ intent: "forecast", label: "Forecast" }],
        },
      }),
      ev("done", { summary: "Pick one", status: "completed" }),
    ]);
    const assistant = clarified.messages[1];
    if (assistant.role !== "assistant") throw new Error("expected assistant");
    expect(assistant.cards[0]?.type).toBe("clarification");
    expect(assistant.status).toBe("done");
    expect(clarified.sending).toBe(false);

    const cancelled = apply(startThread(), [ev("cancelled")]);
    const cancelledMsg = cancelled.messages[1];
    if (cancelledMsg.role !== "assistant") throw new Error("expected assistant");
    expect(cancelledMsg.status).toBe("cancelled");

    const errored = apply(startThread(), [ev("error", { message: "down", code: "internal_error" })]);
    const errorMsg = errored.messages[1];
    if (errorMsg.role !== "assistant") throw new Error("expected assistant");
    expect(errorMsg.status).toBe("error");
    expect(errorMsg.error).toBe("down");
  });

  it("shows connection lost until restore", () => {
    let state = startThread();
    state = chatReducer(state, { type: "connection_lost" });
    const lost = state.messages[1];
    if (lost.role !== "assistant") throw new Error("expected assistant");
    expect(lost.connectionLost).toBe(true);
    state = chatReducer(state, { type: "connection_restored" });
    const restored = state.messages[1];
    if (restored.role !== "assistant") throw new Error("expected assistant");
    expect(restored.connectionLost).toBe(false);
  });

  it("updates suggestion cards in place", () => {
    const withCard = apply(startThread(), [
      ev("card", {
        card: { type: "po_suggestion", message: "Draft PO", data: { lines: [] } },
      }),
    ]);
    const assistant = withCard.messages[1];
    if (assistant.role !== "assistant") throw new Error("expected assistant");
    const cardId = assistant.cards[0]?.id;
    expect(cardId).toBeTruthy();
    const decided = chatReducer(withCard, {
      type: "set_suggestion",
      cardId: cardId ?? "",
      status: "approved",
    });
    const next = decided.messages[1];
    if (next.role !== "assistant") throw new Error("expected assistant");
    expect(next.cards[0]?.suggestionStatus).toBe("approved");
  });
});
