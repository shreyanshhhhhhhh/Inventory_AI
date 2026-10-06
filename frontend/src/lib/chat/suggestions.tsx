"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { chatApi } from "@/lib/chat/api";
import { asRecords, asString } from "@/lib/chat/card-data";
import type { OrchestratorCard } from "@/lib/chat/types";

export type InboxSuggestion = {
  id: string;
  suggestionId: string | null;
  runId: string;
  kind: "po" | "email";
  title: string;
  summary: string;
  status: "pending" | "approved" | "rejected";
};

type InboxSuggestionsValue = {
  items: InboxSuggestion[];
  pendingCount: number;
  upsertFromCard: (runId: string, card: OrchestratorCard) => void;
  setStatus: (id: string, status: "approved" | "rejected") => void;
};

const InboxSuggestionsContext = createContext<InboxSuggestionsValue | null>(null);

function titleFor(card: OrchestratorCard): string {
  if (card.type === "po_suggestion") return "Draft purchase order";
  if (card.type === "email_draft") return "Draft supplier email";
  return card.message || "Agent suggestion";
}

export function InboxSuggestionsProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<InboxSuggestion[]>([]);

  const upsertFromCard = useCallback((runId: string, card: OrchestratorCard) => {
    if (card.type !== "po_suggestion" && card.type !== "email_draft") return;
    const records = card.type === "po_suggestion" ? asRecords(card.data.suggestions) : [];
    const incoming: InboxSuggestion[] =
      records.length > 0
        ? records.flatMap((row) => {
            const suggestionId = asString(row.id);
            if (!suggestionId) return [];
            const rowStatus = asString(row.status);
            return [
              {
                id: suggestionId,
                suggestionId,
                runId,
                kind: "po" as const,
                title: asString(row.supplier_name)
                  ? `Draft PO for ${asString(row.supplier_name)}`
                  : titleFor(card),
                summary: card.message || "Waiting for review.",
                status:
                  rowStatus === "approved" || rowStatus === "rejected" ? rowStatus : "pending",
              },
            ];
          })
        : [
            {
              id: card.id,
              suggestionId: asString(card.data.suggestion_id) || null,
              runId,
              kind: card.type === "po_suggestion" ? "po" : "email",
              title: titleFor(card),
              summary: card.message || "Waiting for review.",
              status: card.suggestionStatus ?? "pending",
            },
          ];
    setItems((current) => {
      let next = current;
      for (const item of incoming) {
        const index = next.findIndex((row) => row.id === item.id);
        if (index < 0) {
          next = [...next, item];
          continue;
        }
        const prev = next[index];
        if (prev.status !== "pending") continue;
        if (prev.summary === item.summary && prev.title === item.title && prev.status === item.status) {
          continue;
        }
        const copy = [...next];
        copy[index] = { ...prev, ...item, status: item.status === "pending" ? prev.status : item.status };
        next = copy;
      }
      return next;
    });
  }, []);

  const setStatus = useCallback((id: string, status: "approved" | "rejected") => {
    const item = items.find((row) => row.id === id || row.suggestionId === id);
    const suggestionId = item?.suggestionId;
    void (async () => {
      if (item?.kind === "po" && suggestionId) {
        try {
          if (status === "approved") await chatApi.approveSuggestion(suggestionId);
          else await chatApi.rejectSuggestion(suggestionId, "Rejected by the owner.");
        } catch {
          return;
        }
      }
      setItems((current) =>
        current.map((row) =>
          row.id === (item?.id ?? id) || (suggestionId !== null && suggestionId !== undefined && row.suggestionId === suggestionId)
            ? { ...row, status }
            : row,
        ),
      );
    })();
  }, [items]);

  const value = useMemo<InboxSuggestionsValue>(() => {
    return {
      items,
      pendingCount: items.filter((item) => item.status === "pending").length,
      upsertFromCard,
      setStatus,
    };
  }, [items, upsertFromCard, setStatus]);

  return (
    <InboxSuggestionsContext.Provider value={value}>
      {children}
    </InboxSuggestionsContext.Provider>
  );
}

export function useInboxSuggestions(): InboxSuggestionsValue {
  const context = useContext(InboxSuggestionsContext);
  if (!context) {
    throw new Error("useInboxSuggestions must be used within InboxSuggestionsProvider");
  }
  return context;
}
