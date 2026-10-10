"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";

import { chatApi, streamChatEvents } from "@/lib/chat/api";
import { chatReducer, hydrateFromDetailEvents, initialChatState } from "@/lib/chat/reducer";
import type { ChatSseEvent, ChatUiState, PlanState } from "@/lib/chat/types";

function newId(): string {
  return crypto.randomUUID();
}

export function useChatSession(): {
  state: ChatUiState;
  send: (text: string) => Promise<void>;
  stop: () => Promise<void>;
  retryLast: () => Promise<void>;
  approvePlan: (action: "run" | "edit" | "cancel", plan?: PlanState) => Promise<void>;
  setSuggestion: (cardId: string, status: "approved" | "rejected") => void;
} {
  const [state, dispatch] = useReducer(chatReducer, initialChatState);
  const abortRef = useRef<AbortController | null>(null);
  const runIdRef = useRef<string | null>(null);
  const reconnectingRef = useRef(false);
  const lastUserRef = useRef<string>("");

  const listen = useCallback(async (runId: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    runIdRef.current = runId;

    const onEvent = (event: ChatSseEvent) => {
      dispatch({ type: "event", event });
    };

    const pump = async (): Promise<void> => {
      const result = await streamChatEvents(
        runId,
        controller.signal,
        onEvent,
        () => dispatch({ type: "connection_lost" }),
      );
      if (controller.signal.aborted) return;
      if (result === "closed") {
        try {
          const detail = await chatApi.getRun(runId);
          dispatch({
            type: "hydrate_events",
            events: hydrateFromDetailEvents(detail.events),
          });
        } catch {
          // Keep the live SSE state if the run detail cannot be loaded.
        }
        dispatch({ type: "unlock" });
        return;
      }
      if (result === "dropped") {
        reconnectingRef.current = true;
        dispatch({ type: "connection_lost" });
        await new Promise((resolve) => window.setTimeout(resolve, 800));
        if (controller.signal.aborted) return;
        try {
          const detail = await chatApi.getRun(runId);
          dispatch({
            type: "hydrate_events",
            events: hydrateFromDetailEvents(detail.events),
          });
          dispatch({ type: "connection_restored" });
          if (detail.status === "running" || detail.status === "awaiting_approval") {
            await pump();
          } else {
            dispatch({ type: "unlock" });
          }
        } catch {
          await pump();
        }
      }
    };

    await pump();
  }, []);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      lastUserRef.current = trimmed;
      const createdAt = new Date().toISOString();
      dispatch({ type: "user_sent", messageId: newId(), text: trimmed, createdAt });
      dispatch({ type: "assistant_placeholder", messageId: newId(), createdAt });
      try {
        const run = await chatApi.startRun(trimmed);
        dispatch({ type: "run_started", runId: run.id });
        await listen(run.id);
      } catch (error) {
        dispatch({
          type: "event",
          event: {
            type: "error",
            run_id: "local",
            ts: new Date().toISOString(),
            payload: {
              message: error instanceof Error ? error.message : "Could not start the run.",
            },
          },
        });
        dispatch({ type: "unlock" });
      }
    },
    [listen],
  );

  const stop = useCallback(async () => {
    const runId = runIdRef.current;
    if (!runId) return;
    try {
      await chatApi.cancel(runId);
    } catch {
      dispatch({
        type: "event",
        event: {
          type: "cancelled",
          run_id: runId,
          ts: new Date().toISOString(),
          payload: {},
        },
      });
    }
  }, []);

  const retryLast = useCallback(async () => {
    if (lastUserRef.current) await send(lastUserRef.current);
  }, [send]);

  const approvePlan = useCallback(async (action: "run" | "edit" | "cancel", plan?: PlanState) => {
    const runId = runIdRef.current;
    if (!runId) return;
    if (action === "cancel") {
      await chatApi.cancel(runId);
      return;
    }
    await chatApi.resume(runId, {
      action,
      plan: plan
        ? {
            steps: plan.steps.map((step) => ({
              id: step.id,
              agent: step.agent,
              task: step.task,
              depends_on: step.depends_on,
              is_write: step.is_write,
            })),
          }
        : undefined,
    });
    await listen(runId);
  }, [listen]);

  const setSuggestion = useCallback((cardId: string, status: "approved" | "rejected") => {
    dispatch({ type: "set_suggestion", cardId, status });
  }, []);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  return { state, send, stop, retryLast, approvePlan, setSuggestion };
}
