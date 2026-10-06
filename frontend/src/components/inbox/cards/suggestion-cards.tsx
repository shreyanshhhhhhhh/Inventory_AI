"use client";

import { useEffect, useState } from "react";

import { WhyButton } from "@/components/inbox/cards/explanation-cards";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { asRecords, asString } from "@/lib/chat/card-data";
import { chatApi } from "@/lib/chat/api";
import { useInboxSuggestions } from "@/lib/chat/suggestions";
import type { OrchestratorCard } from "@/lib/chat/types";

function useCardStatus(card: OrchestratorCard): "pending" | "approved" | "rejected" {
  const { items } = useInboxSuggestions();
  return items.find((item) => item.id === card.id)?.status ?? card.suggestionStatus ?? "pending";
}

export function PoSuggestionCard({
  card,
  onDecide,
  onAskWhy,
}: {
  card: OrchestratorCard;
  onDecide: (status: "approved" | "rejected") => void;
  onAskWhy?: (value: string) => void;
}) {
  const lines = asRecords(card.data.lines);
  const status = useCardStatus(card);
  const suggestionId =
    asString(card.data.suggestion_id) || asString(asRecords(card.data.suggestions)[0]?.id);
  return (
    <article className="rounded-xl border bg-card p-3 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-medium">Purchase order suggestion</h4>
        <div className="flex items-center gap-2">
          <WhyButton onAsk={onAskWhy} command={suggestionId ? `/why suggestion ${suggestionId}` : ""} />
          <span className="text-xs text-muted-foreground">{status}</span>
        </div>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{card.message}</p>
      {lines.length > 0 ? (
        <ul className="mt-2 space-y-1 text-xs">
          {lines.map((line, index) => (
            <li key={asString(line.product_id) || String(index)}>
              {asString(line.sku) || asString(line.product_id)} · qty {asString(line.quantity)}
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
  onAskWhy,
}: {
  card: OrchestratorCard;
  onDecide: (status: "approved" | "rejected") => void;
  onAskWhy?: (value: string) => void;
}) {
  const [subject, setSubject] = useState(asString(card.data.subject) || "");
  const [body, setBody] = useState(asString(card.data.body) || card.message);
  const [banner, setBanner] = useState(asString(card.data.banner));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"send" | "save" | "reject" | null>(null);
  const status = useCardStatus(card);
  const messageId = asString(card.data.message_id);
  const pending = status === "pending";

  useEffect(() => {
    if (card.data.console_mode === true) {
      setBanner(
        asString(card.data.banner) ||
          "Console email mode is on. Drafts are logged and are never delivered.",
      );
      return;
    }
    void chatApi
      .getEmailSenderStatus()
      .then((row) => {
        if (row.console_mode && row.banner) setBanner(row.banner);
      })
      .catch(() => undefined);
  }, [card.data.banner, card.data.console_mode]);

  async function run(kind: "send" | "save" | "reject") {
    if (!messageId) {
      onDecide(kind === "reject" ? "rejected" : "approved");
      return;
    }
    setBusy(kind);
    setError(null);
    try {
      if (kind === "send") {
        await chatApi.sendSupplierMessage(messageId, { subject, body });
        onDecide("approved");
      } else if (kind === "save") {
        await chatApi.saveSupplierDraft(messageId, { subject, body });
      } else {
        await chatApi.rejectSupplierMessage(messageId, "Rejected by the owner.");
        onDecide("rejected");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update this draft.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <article className="rounded-xl border bg-card p-3 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-medium">Email draft</h4>
        <div className="flex items-center gap-2">
          <WhyButton
            onAsk={onAskWhy}
            command={asString(card.data.suggestion_id) ? `/why suggestion ${asString(card.data.suggestion_id)}` : ""}
          />
          <span className="text-xs text-muted-foreground">{status}</span>
        </div>
      </div>
      {banner ? (
        <p className="mt-2 rounded-md border border-amber-300 bg-amber-50 px-2 py-1 text-xs text-amber-950 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100">
          {banner}
        </p>
      ) : null}
      <p className="mt-1 text-xs text-muted-foreground">
        To {asString(card.data.to_email) || "supplier"}
        {asString(card.data.kind) ? ` · ${asString(card.data.kind)}` : ""}
      </p>
      {pending ? (
        <>
          <Input
            className="mt-2"
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
            aria-label="Email subject"
          />
          <Textarea
            className="mt-2 min-h-32"
            value={body}
            onChange={(event) => setBody(event.target.value)}
            aria-label="Email body"
          />
        </>
      ) : (
        <>
          <p className="mt-2 text-sm font-medium">{subject || "No subject"}</p>
          <p className="mt-2 whitespace-pre-wrap text-sm">{body || "No body yet."}</p>
        </>
      )}
      {error ? <p className="mt-2 text-xs text-destructive">{error}</p> : null}
      {pending ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" disabled={busy !== null} onClick={() => void run("send")}>
            {busy === "send" ? "Sending…" : "Approve and Send"}
          </Button>
          <Button size="sm" variant="outline" disabled={busy !== null} onClick={() => void run("save")}>
            {busy === "save" ? "Saving…" : "Save draft"}
          </Button>
          <Button
            size="sm"
            variant="destructive"
            disabled={busy !== null}
            onClick={() => void run("reject")}
          >
            Reject
          </Button>
        </div>
      ) : null}
    </article>
  );
}
