"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type { OrchestratorCard } from "@/lib/chat/types";

export type InboxSuggestion = {
  id: string;
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
    setItems((current) => {
      const next: InboxSuggestion = {
        id: card.id,
        runId,
        kind: card.type === "po_suggestion" ? "po" : "email",
        title: titleFor(card),
        summary: card.message || "Waiting for review.",
        status: card.suggestionStatus ?? "pending",
      };
      const index = current.findIndex((item) => item.id === card.id);
      if (index < 0) return [...current, next];
      const prev = current[index];
      if (prev.status !== "pending") return current;
      if (prev.summary === next.summary && prev.title === next.title) {
        return current;
      }
      const copy = [...current];
      copy[index] = { ...copy[index], ...next };
      return copy;
    });
  }, []);

  const setStatus = useCallback((id: string, status: "approved" | "rejected") => {
    setItems((current) =>
      current.map((item) => (item.id === id ? { ...item, status } : item)),
    );
  }, []);

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
