"use client";

import { useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { Bot } from "lucide-react";

import { ChatInput, SuggestedChips } from "@/components/inbox/chat-input";
import { ChatThread } from "@/components/inbox/chat-thread";
import { asString } from "@/lib/chat/card-data";
import { useInboxSuggestions } from "@/lib/chat/suggestions";
import { useChatSession } from "@/lib/chat/use-chat-session";

export function ChatPanel() {
  const { state, send, stop, retryLast, approvePlan, setSuggestion } = useChatSession();
  const { upsertFromCard, setStatus } = useInboxSuggestions();
  const running = Boolean(state.activeRunId) || state.sending;
  const searchParams = useSearchParams();
  const askedRef = useRef<string | null>(null);

  useEffect(() => {
    for (const message of state.messages) {
      if (message.role !== "assistant" || !message.runId) continue;
      for (const card of message.cards) {
        upsertFromCard(message.runId, card);
      }
    }
  }, [state.messages, upsertFromCard]);

  useEffect(() => {
    const ask = searchParams.get("ask")?.trim();
    if (!ask || askedRef.current === ask || running) return;
    askedRef.current = ask;
    void send(ask);
  }, [running, searchParams, send]);

  return (
    <div className="flex min-h-[min(70vh,720px)] flex-col gap-3 overflow-hidden">
      {state.messages.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 rounded-2xl border bg-card/70 px-4 py-10 text-center dark:bg-card/40">
          <Bot className="size-8 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium">Ask the inventory assistant</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Slash commands or plain English. Compound requests run as one plan.
            </p>
          </div>
          <SuggestedChips onPick={(command) => void send(command)} />
        </div>
      ) : (
        <ChatThread
          messages={state.messages}
          onChoose={(value) => void send(value)}
          onRetry={() => void retryLast()}
          onSuggest={(card, status) => {
            setSuggestion(card.id, status);
            const suggestionId = asString(card.data.suggestion_id);
            setStatus(suggestionId || card.id, status);
          }}
          onAskWhy={(value) => void send(value)}
          onRunPlan={() => void approvePlan("run")}
          onCancelPlan={() => void approvePlan("cancel")}
          onEditPlan={(plan) => void approvePlan("edit", plan)}
        />
      )}
      <ChatInput
        disabled={running}
        running={running}
        onSend={(text) => void send(text)}
        onStop={() => void stop()}
      />
    </div>
  );
}
