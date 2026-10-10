"use client";

import { LoaderCircle } from "lucide-react";

export function ThinkingBubble({ message }: { message: string }) {
  return (
    <div
      className="flex max-w-[85%] items-start gap-2 rounded-2xl rounded-bl-md border bg-card px-3 py-2 text-sm shadow-sm transition-colors dark:bg-card/80"
      aria-live="polite"
    >
      <span className="mt-1 flex gap-0.5" aria-hidden>
        <span className="chat-think-dot size-1.5 rounded-full bg-foreground/70" />
        <span className="chat-think-dot size-1.5 rounded-full bg-foreground/70 [animation-delay:150ms]" />
        <span className="chat-think-dot size-1.5 rounded-full bg-foreground/70 [animation-delay:300ms]" />
      </span>
      <span className="text-muted-foreground">{message}</span>
      <LoaderCircle className="mt-0.5 size-3.5 animate-spin text-muted-foreground" />
    </div>
  );
}
