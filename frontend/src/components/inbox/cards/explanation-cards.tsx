"use client";

import { asRecords, asString } from "@/lib/chat/card-data";
import type { OrchestratorCard } from "@/lib/chat/types";

function EvidencePanel({
  rows,
}: {
  rows: Array<{ field: string; value: string; source: string }>;
}) {
  if (rows.length === 0) return null;
  return (
    <details className="mt-2 rounded-md border bg-muted/30 px-2 py-1">
      <summary className="cursor-pointer text-xs font-medium">Evidence</summary>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="text-muted-foreground">
            <tr>
              <th className="py-1 font-medium">Field</th>
              <th className="py-1 font-medium">Value</th>
              <th className="py-1 font-medium">Source</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.field}-${row.source}`} className="border-t">
                <td className="py-1 pr-2 font-mono">{row.field}</td>
                <td className="py-1 pr-2">{row.value}</td>
                <td className="py-1 text-muted-foreground">{row.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function ExplanationCard({ card }: { card: OrchestratorCard }) {
  const citations = asRecords(card.data.citations).map((row) => ({
    field: asString(row.field),
    value: asString(row.value),
    source: asString(row.source),
  }));
  const missing = Array.isArray(card.data.missing)
    ? card.data.missing.filter((item): item is string => typeof item === "string")
    : [];
  return (
    <article className="rounded-xl border bg-card p-3 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-medium">Why</h4>
        {asString(card.data.confidence) ? (
          <span className="text-xs text-muted-foreground">{asString(card.data.confidence)} confidence</span>
        ) : null}
      </div>
      <p className="mt-2 text-sm">{card.message}</p>
      {asString(card.data.what_would_change) ? (
        <p className="mt-2 text-xs text-muted-foreground">{asString(card.data.what_would_change)}</p>
      ) : null}
      {missing.length > 0 ? (
        <p className="mt-2 text-xs text-muted-foreground">Missing: {missing.join(", ")}</p>
      ) : null}
      <EvidencePanel rows={citations} />
    </article>
  );
}

function sideValue(side: Record<string, unknown> | undefined, key: string): string {
  if (!side) return "—";
  const value = side[key];
  if (value === null || value === undefined || value === "") return "none";
  return String(value);
}

export function WhatIfCompareCard({ card }: { card: OrchestratorCard }) {
  const items = asRecords(card.data.items);
  return (
    <article className="rounded-xl border bg-card p-3 shadow-sm">
      <h4 className="text-sm font-medium">What-if comparison</h4>
      <p className="mt-1 text-sm">{card.message}</p>
      {items.length === 0 ? (
        <p className="mt-2 text-xs text-muted-foreground">No before/after rows for this scenario.</p>
      ) : (
        <div className="mt-3 space-y-2">
          {items.map((item, index) => {
            const before = item.before && typeof item.before === "object" && !Array.isArray(item.before)
              ? (item.before as Record<string, unknown>)
              : undefined;
            const after = item.after && typeof item.after === "object" && !Array.isArray(item.after)
              ? (item.after as Record<string, unknown>)
              : undefined;
            return (
              <div key={asString(item.product_id) || String(index)} className="rounded-lg border px-2 py-2">
                <p className="text-xs font-medium">
                  {asString(item.sku) || asString(item.product_name) || "SKU"}
                </p>
                <table className="mt-1 w-full text-left text-xs">
                  <thead className="text-muted-foreground">
                    <tr>
                      <th className="py-1 font-medium">Metric</th>
                      <th className="py-1 font-medium">Before</th>
                      <th className="py-1 font-medium">After</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-t">
                      <td className="py-1">Stockout date</td>
                      <td className="py-1">{sideValue(before, "stockout_date")}</td>
                      <td className="py-1">{sideValue(after, "stockout_date")}</td>
                    </tr>
                    <tr className="border-t">
                      <td className="py-1">Recommended qty</td>
                      <td className="py-1">{sideValue(before, "recommended_quantity")}</td>
                      <td className="py-1">{sideValue(after, "recommended_quantity")}</td>
                    </tr>
                    <tr className="border-t">
                      <td className="py-1">Cost</td>
                      <td className="py-1">{sideValue(before, "cost")}</td>
                      <td className="py-1">{sideValue(after, "cost")}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            );
          })}
        </div>
      )}
    </article>
  );
}

export function WhyButton({ onAsk, command }: { onAsk?: (value: string) => void; command: string }) {
  if (!onAsk || !command) return null;
  return (
    <button
      type="button"
      className="text-xs font-medium text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
      onClick={() => onAsk(command)}
    >
      Why?
    </button>
  );
}
