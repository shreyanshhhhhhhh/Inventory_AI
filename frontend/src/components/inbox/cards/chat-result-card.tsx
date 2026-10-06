"use client";

import type { OrchestratorCard } from "@/lib/chat/types";
import {
  ClarificationCard,
  ErrorCard,
  ExceptionListCard,
  StockTableCard,
  TextResultCard,
} from "@/components/inbox/cards/result-cards";
import { ForecastChartCard } from "@/components/inbox/cards/forecast-chart-card";
import { EmailDraftCard, PoSuggestionCard } from "@/components/inbox/cards/suggestion-cards";

export function ChatResultCard({
  card,
  onChoose,
  onRetry,
  onSuggest,
}: {
  card: OrchestratorCard;
  onChoose: (value: string) => void;
  onRetry: () => void;
  onSuggest: (card: OrchestratorCard, status: "approved" | "rejected") => void;
}) {
  if (card.type === "stock_table") return <StockTableCard card={card} />;
  if (card.type === "forecast_chart") return <ForecastChartCard card={card} />;
  if (card.type === "exception_list") return <ExceptionListCard card={card} />;
  if (card.type === "po_suggestion") {
    return <PoSuggestionCard card={card} onDecide={(status) => onSuggest(card, status)} />;
  }
  if (card.type === "email_draft") {
    return <EmailDraftCard card={card} onDecide={(status) => onSuggest(card, status)} />;
  }
  if (card.type === "clarification" || card.type === "refusal") {
    return <ClarificationCard card={card} onChoose={onChoose} />;
  }
  if (card.type === "text" || card.type === "plan") return <TextResultCard card={card} />;
  return <ErrorCard message={card.message || "Unknown card."} onRetry={onRetry} />;
}
