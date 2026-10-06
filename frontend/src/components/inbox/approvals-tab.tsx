"use client";

import { Inbox } from "lucide-react";

import { EmptyState } from "@/components/common/empty-state";
import { Button } from "@/components/ui/button";
import { useInboxSuggestions } from "@/lib/chat/suggestions";

export function ApprovalsTab() {
  const { items, setStatus } = useInboxSuggestions();
  const pending = items.filter((item) => item.status === "pending");
  const decided = items.filter((item) => item.status !== "pending");

  if (items.length === 0) {
    return (
      <EmptyState
        icon={Inbox}
        title="No approval requests"
        message="Draft purchase orders and supplier emails from chat land here for review."
      />
    );
  }

  return (
    <div className="space-y-3">
      {pending.map((item) => (
        <article key={item.id} className="rounded-xl border bg-card p-3 shadow-sm">
          <p className="text-sm font-medium">{item.title}</p>
          <p className="mt-1 text-xs text-muted-foreground">{item.summary}</p>
          <div className="mt-3 flex gap-2">
            <Button size="sm" onClick={() => setStatus(item.id, "approved")}>
              Approve
            </Button>
            <Button size="sm" variant="outline" onClick={() => setStatus(item.id, "rejected")}>
              Reject
            </Button>
          </div>
        </article>
      ))}
      {decided.map((item) => (
        <article key={item.id} className="rounded-xl border bg-muted/30 p-3 text-sm">
          <p className="font-medium">{item.title}</p>
          <p className="text-xs text-muted-foreground">{item.status}</p>
        </article>
      ))}
    </div>
  );
}
