"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { asRecords, asString } from "@/lib/chat/card-data";
import { useInboxSuggestions } from "@/lib/chat/suggestions";
import type { OrchestratorCard } from "@/lib/chat/types";

function useCardStatus(card: OrchestratorCard): "pending" | "approved" | "rejected" {
  const { items } = useInboxSuggestions();
  return items.find((item) => item.id === card.id)?.status ?? card.suggestionStatus ?? "pending";
}

export function PoSuggestionCard({
  card,
  onDecide,
}: {
  card: OrchestratorCard;
  onDecide: (status: "approved" | "rejected") => void;
}) {
  const lines = asRecords(card.data.lines);
  const status = useCardStatus(card);
  return (
    <article className="rounded-xl border bg-card p-3 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-medium">Purchase order suggestion</h4>
        <span className="text-xs text-muted-foreground">{status}</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{card.message}</p>
      {lines.length > 0 ? (
        <ul className="mt-2 space-y-1 text-xs">
          {lines.map((line, index) => (
            <li key={asString(line.product_id) || String(index)}>
              {asString(line.product_id)} · qty {asString(line.quantity)}
            </li>
          ))}
        </ul>
      ) : null}
      {status === "pending" ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" onClick={() => onDecide("approved")}>
            Approve
          </Button>
          <Button size="sm" variant="outline" onClick={() => onDecide("rejected")}>
            Reject
          </Button>
        </div>
      ) : null}
    </article>
  );
}

export function EmailDraftCard({
  card,
  onDecide,
}: {
  card: OrchestratorCard;
  onDecide: (status: "approved" | "rejected") => void;
}) {
  const [editing, setEditing] = useState(false);
  const [body, setBody] = useState(asString(card.data.body) || card.message);
  const status = useCardStatus(card);
  return (
    <article className="rounded-xl border bg-card p-3 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-medium">Email draft</h4>
        <span className="text-xs text-muted-foreground">{status}</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        To {asString(card.data.to_email) || "supplier"} · {asString(card.data.subject) || "No subject"}
      </p>
      {editing ? (
        <Textarea className="mt-2" value={body} onChange={(event) => setBody(event.target.value)} />
      ) : (
        <p className="mt-2 whitespace-pre-wrap text-sm">{body || "No body yet."}</p>
      )}
      {status === "pending" ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" onClick={() => onDecide("approved")}>
            Approve
          </Button>
          <Button size="sm" variant="outline" onClick={() => setEditing((value) => !value)}>
            {editing ? "Done" : "Edit"}
          </Button>
          <Button size="sm" variant="destructive" onClick={() => onDecide("rejected")}>
            Reject
          </Button>
        </div>
      ) : null}
    </article>
  );
}
