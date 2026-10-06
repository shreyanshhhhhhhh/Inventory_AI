"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Skeleton } from "@/components/ui/skeleton";
import { asNumber, asRecords, asString } from "@/lib/chat/card-data";
import type { OrchestratorCard } from "@/lib/chat/types";

export function ForecastChartCard({ card }: { card: OrchestratorCard }) {
  const points = asRecords(card.data.points).map((point) => ({
    label: asString(point.label) || asString(point.date),
    value: asNumber(point.value) ?? asNumber(point.units) ?? 0,
  }));
  const items = asRecords(card.data.items);
  const series =
    points.length > 0
      ? points
      : items.map((item) => ({
          label: asString(item.sku) || asString(item.product_name),
          value: asNumber(item.forecast_units) ?? 0,
        }));

  return (
    <article className="rounded-xl border bg-card p-3 shadow-sm">
      <h4 className="text-sm font-medium">Forecast</h4>
      {series.length === 0 ? (
        <div className="mt-3 space-y-2">
          <Skeleton className="h-28 w-full" />
          <p className="text-xs text-muted-foreground">
            {card.message || "Forecast chart data is not available yet."}
          </p>
        </div>
      ) : (
        <div className="mt-3 h-40">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={series}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11 }} width={32} />
              <Tooltip />
              <Area type="monotone" dataKey="value" stroke="var(--chart-2)" fill="var(--chart-2)" fillOpacity={0.2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </article>
  );
}
