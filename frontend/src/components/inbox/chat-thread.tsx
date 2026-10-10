"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowDown, Copy } from "lucide-react";
import { toast } from "sonner";

import { AgentTimeline } from "@/components/inbox/agent-timeline";
import { ChatResultCard } from "@/components/inbox/cards/chat-result-card";
import { ErrorCard } from "@/components/inbox/cards/result-cards";
import { PlanCard } from "@/components/inbox/plan-card";
import { ThinkingBubble } from "@/components/inbox/thinking-bubble";
import { Button } from "@/components/ui/button";
import type { ChatThreadMessage, OrchestratorCard, PlanState } from "@/lib/chat/types";
import { cn } from "@/lib/utils";

function copyTrace(message: Extract<ChatThreadMessage, { role: "assistant" }>) {
  const payload = {
    runId: message.runId,
    status: message.status,
    events: message.events,
    plan: message.plan,
    timeline: message.timeline,
  };
  void navigator.clipboard.writeText(JSON.stringify(payload, null, 2)).then(
    () => toast.success("Trace copied"),
    () => toast.error("Could not copy trace"),
  );
}

export function ChatThread({
  messages,
  onChoose,
  onRetry,
  onSuggest,
  onAskWhy,
  onRunPlan,
  onCancelPlan,
  onEditPlan,
}: {
  messages: ChatThreadMessage[];
  onChoose: (value: string) => void;
  onRetry: () => void;
  onSuggest: (card: OrchestratorCard, status: "approved" | "rejected") => void;
  onAskWhy?: (value: string) => void;
  onRunPlan: () => void;
  onCancelPlan: () => void;
  onEditPlan: (plan: PlanState) => void;
}) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const pinnedRef = useRef(true);
  const [showJump, setShowJump] = useState(false);

  useEffect(() => {
    const node = scrollerRef.current;
    if (!node || !pinnedRef.current) return;
    node.scrollTop = node.scrollHeight;
  }, [messages]);

  function onScroll() {
    const node = scrollerRef.current;
    if (!node) return;
    const distance = node.scrollHeight - node.scrollTop - node.clientHeight;
    pinnedRef.current = distance < 64;
    setShowJump(!pinnedRef.current);
  }

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <div
        ref={scrollerRef}
        onScroll={onScroll}
        className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1"
        aria-live="polite"
      >
        {messages.map((message) =>
          message.role === "user" ? (
            <div key={message.id} className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-3 py-2 text-sm text-primary-foreground">
                {message.text}
              </div>
            </div>
          ) : (
            <AssistantBubble
              key={message.id}
              message={message}
              onChoose={onChoose}
              onRetry={onRetry}
              onSuggest={onSuggest}
              onAskWhy={onAskWhy}
              onRunPlan={onRunPlan}
              onCancelPlan={onCancelPlan}
              onEditPlan={onEditPlan}
            />
          ),
        )}
      </div>
      {showJump ? (
        <Button
          size="sm"
          className="absolute bottom-2 left-1/2 -translate-x-1/2 rounded-full shadow-md"
          onClick={() => {
            pinnedRef.current = true;
            setShowJump(false);
            const node = scrollerRef.current;
            if (node) node.scrollTop = node.scrollHeight;
          }}
        >
          <ArrowDown className="size-3.5" />
          Jump to latest
        </Button>
      ) : null}
    </div>
  );
}

function AssistantBubble({
  message,
  onChoose,
  onRetry,
  onSuggest,
  onAskWhy,
  onRunPlan,
  onCancelPlan,
  onEditPlan,
}: {
  message: Extract<ChatThreadMessage, { role: "assistant" }>;
  onChoose: (value: string) => void;
  onRetry: () => void;
  onSuggest: (card: OrchestratorCard, status: "approved" | "rejected") => void;
  onAskWhy?: (value: string) => void;
  onRunPlan: () => void;
  onCancelPlan: () => void;
  onEditPlan: (plan: PlanState) => void;
}) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[92%] space-y-2 sm:max-w-[85%]">
        {message.connectionLost ? (
          <p className="text-xs text-amber-700 dark:text-amber-400">Connection lost, retrying…</p>
        ) : null}
        {message.thinking ? <ThinkingBubble message={message.thinking} /> : null}
        {message.plan ? (
          <PlanCard
            plan={message.plan}
            collapsed={message.status === "done"}
            onRun={onRunPlan}
            onCancel={onCancelPlan}
            onEdit={onEditPlan}
          />
        ) : null}
        {message.text || message.streaming ? (
          <div
            className={cn(
              "rounded-2xl rounded-bl-md border bg-card px-3 py-2 text-sm shadow-sm dark:bg-card/80",
              message.streaming && "chat-cursor",
            )}
          >
            {message.text || (message.streaming ? "" : "")}
          </div>
        ) : null}
        {message.cards.map((card) => (
          <ChatResultCard
            key={card.id}
            card={card}
            onChoose={onChoose}
            onRetry={onRetry}
            onSuggest={onSuggest}
            onAskWhy={onAskWhy}
          />
        ))}
        {message.status === "error" && message.error ? (
          <ErrorCard message={message.error} onRetry={onRetry} />
        ) : null}
        {message.status === "cancelled" ? (
          <p className="text-xs text-muted-foreground">Run cancelled.</p>
        ) : null}
        <div className="flex flex-wrap items-center gap-2">
          {message.timeline.length > 0 || message.runId ? (
            <AgentTimeline items={message.timeline} runId={message.runId} />
          ) : null}
          {message.runId ? (
            <Button
              type="button"
              size="xs"
              variant="ghost"
              aria-label="Copy trace"
              onClick={() => copyTrace(message)}
            >
              <Copy className="size-3" />
              Copy trace
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
