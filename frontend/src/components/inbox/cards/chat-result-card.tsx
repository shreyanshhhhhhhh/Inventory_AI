"use client";

import { ExplanationCard, WhatIfCompareCard } from "@/components/inbox/cards/explanation-cards";
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
  onAskWhy,
}: {
  card: OrchestratorCard;
  onChoose: (value: string) => void;
  onRetry: () => void;
  onSuggest: (card: OrchestratorCard, status: "approved" | "rejected") => void;
  onAskWhy?: (value: string) => void;
}) {
  if (card.type === "stock_table") return <StockTableCard card={card} />;
  if (card.type === "forecast_chart") return <ForecastChartCard card={card} />;
  if (card.type === "exception_list") return <ExceptionListCard card={card} onAskWhy={onAskWhy} />;
  if (card.type === "po_suggestion") {
    return (
      <PoSuggestionCard
        card={card}
        onDecide={(status) => onSuggest(card, status)}
        onAskWhy={onAskWhy}
      />
    );
  }
  if (card.type === "email_draft") {
    return (
      <EmailDraftCard
        card={card}
        onDecide={(status) => onSuggest(card, status)}
        onAskWhy={onAskWhy}
      />
    );
  }
  if (card.type === "explanation") return <ExplanationCard card={card} />;
  if (card.type === "whatif_compare") return <WhatIfCompareCard card={card} />;
  if (card.type === "clarification" || card.type === "refusal") {
    return <ClarificationCard card={card} onChoose={onChoose} />;
  }
  if (card.type === "text" || card.type === "plan") return <TextResultCard card={card} />;
  return <ErrorCard message={card.message || "Unknown card."} onRetry={onRetry} />;
}
