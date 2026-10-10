"use client";

import { WhyButton } from "@/components/inbox/cards/explanation-cards";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { asRecords, asString } from "@/lib/chat/card-data";
import { intentToCommand } from "@/lib/chat/commands";
import type { OrchestratorCard } from "@/lib/chat/types";

export function StockTableCard({ card }: { card: OrchestratorCard }) {
  const items = asRecords(card.data.items);
  return (
    <article className="rounded-xl border bg-card p-3 shadow-sm">
      <h4 className="text-sm font-medium">Stock</h4>
      {items.length === 0 ? (
        <div className="mt-3 space-y-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <p className="text-xs text-muted-foreground">
            {card.message || "Stock table data is not available yet."}
          </p>
        </div>
      ) : (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-muted-foreground">
              <tr>
                <th className="py-1 font-medium">SKU</th>
                <th className="py-1 font-medium">Name</th>
                <th className="py-1 font-medium">On hand</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, index) => (
                <tr key={asString(item.product_id) || String(index)} className="border-t">
                  <td className="py-1.5">{asString(item.sku)}</td>
                  <td className="py-1.5">{asString(item.product_name)}</td>
                  <td className="py-1.5">{asString(item.on_hand)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
  );
}

export function ExceptionListCard({
  card,
  onAskWhy,
}: {
  card: OrchestratorCard;
  onAskWhy?: (value: string) => void;
}) {
  const items = asRecords(card.data.items);
  return (
    <article className="rounded-xl border bg-card p-3 shadow-sm">
      <h4 className="text-sm font-medium">Exceptions</h4>
      {items.length === 0 ? (
        <p className="mt-2 text-xs text-muted-foreground">
          {card.message || "No exceptions in this result."}
        </p>
      ) : (
        <ul className="mt-2 space-y-2">
          {items.map((item, index) => {
            const severity = asString(item.severity) || "medium";
            return (
              <li
                key={asString(item.id) || String(index)}
                className="flex items-start justify-between gap-2 rounded-lg border px-2 py-1.5"
              >
                <p className="text-sm">{asString(item.message) || asString(item.title) || "Exception"}</p>
                <div className="flex shrink-0 items-center gap-2">
                  {asString(item.recommended_action) ? (
                    <span className="text-xs text-muted-foreground">
                      {asString(item.recommended_action)}
                    </span>
                  ) : null}
                  <WhyButton
                    onAsk={onAskWhy}
                    command={asString(item.id) ? `/why exception ${asString(item.id)}` : ""}
                  />
                  <Badge variant={severity === "high" || severity === "critical" ? "destructive" : "secondary"}>
                    {severity}
                  </Badge>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </article>
  );
}

export function TextResultCard({ card }: { card: OrchestratorCard }) {
  return (
    <article className="rounded-xl border bg-card p-3 text-sm shadow-sm">
      {card.message || "No additional detail."}
    </article>
  );
}

export function ClarificationCard({
  card,
  onChoose,
}: {
  card: OrchestratorCard;
  onChoose: (value: string) => void;
}) {
  const options = asRecords(card.data.options);
  const commands = Array.isArray(card.data.supported_commands)
    ? card.data.supported_commands.filter((item): item is string => typeof item === "string")
    : [];
  return (
    <article className="rounded-xl border bg-card p-3 shadow-sm">
      <p className="text-sm">{card.message || "Pick an option."}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {options.map((option, index) => {
          const label = asString(option.label) || asString(option.intent);
          const value = asString(option.intent) || label;
          return (
            <button
              key={`${value}-${index}`}
              type="button"
              className="rounded-full border bg-background px-3 py-1 text-xs font-medium hover:bg-muted"
              onClick={() => onChoose(intentToCommand(value))}
            >
              {label}
            </button>
          );
        })}
        {commands.map((command) => (
          <button
            key={command}
            type="button"
            className="rounded-full border bg-background px-3 py-1 text-xs font-medium hover:bg-muted"
            onClick={() => onChoose(command)}
          >
            {command}
          </button>
        ))}
      </div>
    </article>
  );
}

export function ErrorCard({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <article className="rounded-xl border border-destructive/40 bg-destructive/5 p-3 shadow-sm">
      <p className="text-sm text-destructive">{message}</p>
      <button
        type="button"
        className="mt-2 text-xs font-medium underline"
        onClick={onRetry}
      >
        Retry
      </button>
    </article>
  );
}
