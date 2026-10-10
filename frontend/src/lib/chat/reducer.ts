import { applyEvent } from "@/lib/chat/apply-event";
import { patchAssistant } from "@/lib/chat/plan-state";
import { storedEventToSse } from "@/lib/chat/sse";
import type { ChatSseEvent, ChatUiState, TimelineItem } from "@/lib/chat/types";

export const initialChatState: ChatUiState = {
  messages: [],
  activeRunId: null,
  activeMessageId: null,
  sending: false,
};

export type ChatAction =
  | { type: "user_sent"; messageId: string; text: string; createdAt: string }
  | { type: "assistant_placeholder"; messageId: string; createdAt: string }
  | { type: "run_started"; runId: string }
  | { type: "event"; event: ChatSseEvent }
  | { type: "connection_lost" }
  | { type: "connection_restored" }
  | { type: "hydrate_events"; events: ChatSseEvent[] }
  | { type: "set_suggestion"; cardId: string; status: "approved" | "rejected" }
  | { type: "unlock" };

export function chatReducer(state: ChatUiState, action: ChatAction): ChatUiState {
  switch (action.type) {
    case "user_sent":
      return {
        ...state,
        sending: true,
        messages: [
          ...state.messages,
          { id: action.messageId, role: "user", text: action.text, createdAt: action.createdAt },
        ],
      };
    case "assistant_placeholder":
      return {
        ...state,
        activeMessageId: action.messageId,
        messages: [
          ...state.messages,
          {
            id: action.messageId,
            role: "assistant",
            runId: null,
            text: "",
            thinking: "Thinking...",
            streaming: false,
            status: "thinking",
            plan: null,
            cards: [],
            timeline: [],
            error: null,
            connectionLost: false,
            events: [],
            createdAt: action.createdAt,
          },
        ],
      };
    case "run_started":
      return {
        ...state,
        activeRunId: action.runId,
        messages: state.messages.map((item) =>
          item.role === "assistant" && item.id === state.activeMessageId
            ? { ...item, runId: action.runId }
            : item,
        ),
      };
    case "connection_lost":
      return patchAssistant(state, { connectionLost: true });
    case "connection_restored":
      return patchAssistant(state, { connectionLost: false });
    case "unlock":
      return { ...state, sending: false, activeRunId: null };
    case "set_suggestion":
      return {
        ...state,
        messages: state.messages.map((item) => {
          if (item.role !== "assistant") return item;
          return {
            ...item,
            cards: item.cards.map((card) =>
              card.id === action.cardId ? { ...card, suggestionStatus: action.status } : card,
            ),
          };
        }),
      };
    case "hydrate_events":
      return action.events.reduce(
        (next, event) => chatReducer(next, { type: "event", event }),
        state,
      );
    case "event":
      return applyEvent(state, action.event);
    default:
      return state;
  }
}

export function hydrateFromDetailEvents(events: unknown[]): ChatSseEvent[] {
  return events
    .map((item) => storedEventToSse(item))
    .filter((item): item is ChatSseEvent => item !== null);
}

export function timelineFromRunDetail(events: unknown[]): TimelineItem[] {
  let state = chatReducer(initialChatState, {
    type: "assistant_placeholder",
    messageId: "hydrate",
    createdAt: "",
  });
  state = chatReducer(state, { type: "run_started", runId: "hydrate" });
  state = chatReducer(state, {
    type: "hydrate_events",
    events: hydrateFromDetailEvents(events),
  });
  const message = state.messages.find((item) => item.role === "assistant");
  return message && message.role === "assistant" ? message.timeline : [];
}
