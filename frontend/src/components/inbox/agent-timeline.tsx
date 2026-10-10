"use client";

import { useEffect, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { chatApi } from "@/lib/chat/api";
import { timelineFromRunDetail } from "@/lib/chat/reducer";
import type { TimelineItem } from "@/lib/chat/types";
import { cn } from "@/lib/utils";

function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function AgentTimeline({
  items,
  runId,
}: {
  items: TimelineItem[];
  runId: string | null;
}) {
  const [open, setOpen] = useState(false);
  const [remote, setRemote] = useState<TimelineItem[] | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !runId) return;
    let cancelled = false;
    setLoading(true);
    void chatApi
      .getRun(runId)
      .then((detail) => {
        if (cancelled) return;
        const next = timelineFromRunDetail(detail.events);
        if (next.length > 0) setRemote(next);
      })
      .catch(() => {
        if (!cancelled) setRemote(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, runId]);

  const display = remote && remote.length > 0 ? remote : items;
  if (display.length === 0 && !loading) return null;

  return (
    <div className="mt-2">
      <button
        type="button"
        className="text-xs font-medium text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        What the agents did
      </button>
      <ul className={cn("mt-2 space-y-1.5", !open && "hidden", open && "block")}>
        {loading && display.length === 0 ? (
          <li className="space-y-1">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </li>
        ) : (
          display.map((item) => (
            <li
              key={item.stepId}
              className="rounded-lg border bg-muted/40 px-2.5 py-1.5 text-xs dark:bg-muted/20"
            >
              <p className="font-medium">
                {item.agent} · {item.task}
              </p>
              <p className="text-muted-foreground">
                {item.status} · {formatDuration(item.durationMs)} · {item.tool}
              </p>
              {item.error ? <p className="text-destructive">{item.error}</p> : null}
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
