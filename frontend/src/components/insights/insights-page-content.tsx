"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ChartLine } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { DataTable, type DataTableColumn } from "@/components/common/data-table";
import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";
import { StatCard } from "@/components/common/stat-card";
import { StatusBadge, type StatusBadgeVariant } from "@/components/common/status-badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useDemandForecast,
  type ForecastDetail,
  type ForecastSummary,
} from "@/lib/forecast-hooks";
import { formatQuantity } from "@/lib/format";
import { useReports } from "@/lib/reports-hooks";

const METHOD_LABEL: Record<ForecastSummary["method"], string> = {
  seasonal_naive: "Weekly pattern",
  daily_average: "Daily average",
  no_sales: "No sales yet",
};

const METHOD_BADGE: Record<ForecastSummary["method"], StatusBadgeVariant> = {
  seasonal_naive: "approved",
  daily_average: "severity-low",
  no_sales: "draft",
};

const METHOD_DETAIL: Record<ForecastSummary["method"], string> = {
  seasonal_naive: "Repeats the last 7 days of sales.",
  daily_average: "Fewer than 7 days of sales, so each day uses the average so far.",
  no_sales: "No sales in this window, so the forecast stays at zero.",
};

type ChartPoint = {
  label: string;
  sold: number | null;
  forecast: number | null;
};

function formatChartDate(value: string): string {
  const [year, month, day] = value.split("-").map(Number);
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }).format(new Date(year, month - 1, day));
}

function chartPoints(detail: ForecastDetail): ChartPoint[] {
  const recent = detail.history.slice(-28);
  const points: ChartPoint[] = recent.map((point) => ({
    label: formatChartDate(point.date),
    sold: point.units,
    forecast: null,
  }));
  if (points.length > 0 && detail.forecast.length > 0) {
    points[points.length - 1].forecast = points[points.length - 1].sold;
  }
  for (const point of detail.forecast) {
    points.push({
      label: formatChartDate(point.date),
      sold: null,
      forecast: point.units,
    });
  }
  return points;
}

export function InsightsPageContent() {
  const forecast = useDemandForecast();
  const reports = useReports();
  const router = useRouter();
  const [askWhy, setAskWhy] = useState("");

  const columns: DataTableColumn<ForecastSummary>[] = [
    {
      id: "product",
      header: "Product",
      cell: (row) => (
        <div>
          <p className="font-medium">{row.name}</p>
          <p className="text-xs text-muted-foreground">{row.sku}</p>
        </div>
      ),
    },
    {
      id: "sold",
      header: "Sold",
      className: "text-right",
      cell: (row) => formatQuantity(row.historyUnits),
    },
    {
      id: "forecast",
      header: `Next ${forecast.horizonDays} days`,
      className: "text-right",
      cell: (row) => formatQuantity(row.forecastUnits),
    },
    {
      id: "method",
      header: "Method",
      cell: (row) => (
        <StatusBadge variant={METHOD_BADGE[row.method]} label={METHOD_LABEL[row.method]} />
      ),
    },
  ];

  const forecastedUnits = forecast.items.reduce((sum, item) => sum + item.forecastUnits, 0);
  const withPattern = forecast.items.filter((item) => item.method !== "no_sales").length;
  const waiting = forecast.items.length - withPattern;
  const selected =
    forecast.items.find((item) => item.productId === forecast.selectedId) ?? null;
  const detailReady =
    forecast.detail?.productId === selected?.productId ? forecast.detail : null;

  if (forecast.isLoading) {
    return (
      <>
        <PageHeader
          title="Insights"
          description="Demand for the next two weeks, from sales already on the ledger. This does not place orders."
        />
        <div className="grid gap-4 sm:grid-cols-3">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
        <Skeleton className="h-96 w-full" />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Insights"
        description="Demand for the next two weeks, from sales already on the ledger. This does not place orders."
      />

      {forecast.error ? <p className="text-sm text-destructive">{forecast.error}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle>Ask why</CardTitle>
          <CardDescription>
            Opens Agent Inbox with a grounded explanation. Numbers come from stored evidence, not invented prose.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2 sm:flex-row">
          <Input
            value={askWhy}
            onChange={(event) => setAskWhy(event.target.value)}
            placeholder={
              selected
                ? `/why ${selected.sku}`
                : "Why did you suggest 200 units? or /whatif demand up 20%"
            }
            aria-label="Ask why"
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                const text = askWhy.trim() || (selected ? `/why ${selected.sku}` : "/why");
                router.push(`/inbox?ask=${encodeURIComponent(text)}`);
              }
            }}
          />
          <Button
            type="button"
            onClick={() => {
              const text = askWhy.trim() || (selected ? `/why ${selected.sku}` : "/why");
              router.push(`/inbox?ask=${encodeURIComponent(text)}`);
            }}
          >
            Ask why
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label={`Forecasted units`}
          value={formatQuantity(forecastedUnits)}
          subtext={`Next ${forecast.horizonDays} days, all products`}
          icon={ChartLine}
        />
        <StatCard
          label="Products with a forecast"
          value={String(withPattern)}
          subtext="Weekly pattern or daily average"
        />
        <StatCard
          label="Waiting on sales"
          value={String(waiting)}
          subtext={`No sales in the last ${forecast.historyDays} days`}
        />
      </div>

      {forecast.items.length === 0 ? (
        <EmptyState
          icon={ChartLine}
          title="No products to forecast"
          message="Add products in the catalog and record sales. Forecasts are built only from sale movements."
        />
      ) : (
        <div className="grid gap-4 xl:grid-cols-5">
          <div className="space-y-3 xl:col-span-3">
            <div className="space-y-1">
              <h2 className="text-base font-semibold">Demand by product</h2>
              <p className="text-sm text-muted-foreground">
                Sold units are the last {forecast.historyDays} days. Select a row to see the daily shape.
              </p>
            </div>
            <DataTable
              data={forecast.items}
              columns={columns}
              getRowId={(row) => row.productId}
              searchPlaceholder="Search by product or SKU…"
              pageSize={8}
              onRowClick={(row) => forecast.setSelectedId(row.productId)}
              selectedRowId={forecast.selectedId ?? undefined}
            />
          </div>

          <Card className="xl:col-span-2">
            <CardHeader>
              <CardTitle>{selected?.name ?? "Forecast"}</CardTitle>
              <CardDescription>
                {selected
                  ? `${selected.sku} · ${METHOD_DETAIL[selected.method]}`
                  : "Select a product."}
              </CardDescription>
            </CardHeader>
            <CardContent className="h-80">
              {forecast.detailError ? (
                <p className="text-sm text-destructive">{forecast.detailError}</p>
              ) : null}
              {selected?.method === "no_sales" ? (
                <p className="flex h-full items-center justify-center text-center text-sm text-muted-foreground">
                  No sales in this window yet. A forecast appears after this product sells.
                </p>
              ) : !detailReady ? (
                <Skeleton className="h-full w-full" />
              ) : (
                <div className="flex h-full flex-col gap-3">
                  <div className="flex gap-4 text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-1.5">
                      <span className="size-2 rounded-full bg-[var(--chart-2)]" />
                      Sold
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <span className="size-2 rounded-full bg-[var(--chart-4)]" />
                      Forecast
                    </span>
                  </div>
                  <div className="min-h-0 flex-1">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartPoints(detailReady)}>
                        <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                        <XAxis
                          dataKey="label"
                          tick={{ fontSize: 11 }}
                          interval="preserveStartEnd"
                          minTickGap={24}
                        />
                        <YAxis tick={{ fontSize: 12 }} width={36} />
                        <Tooltip />
                        <Line
                          type="monotone"
                          dataKey="sold"
                          stroke="var(--chart-2)"
                          strokeWidth={2}
                          dot={false}
                          connectNulls={false}
                          name="Sold"
                        />
                        <Line
                          type="monotone"
                          dataKey="forecast"
                          stroke="var(--chart-4)"
                          strokeWidth={2}
                          strokeDasharray="5 4"
                          dot={false}
                          connectNulls={false}
                          name="Forecast"
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Stock movements</CardTitle>
            <CardDescription>Daily receipts and sales for the last 30 days.</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            {reports.isLoading ? (
              <Skeleton className="h-full w-full" />
            ) : reports.movementTrend.every((point) => point.unitsIn === 0 && point.unitsOut === 0) ? (
              <p className="flex h-full items-center justify-center text-sm text-muted-foreground">
                No movement history in this period yet.
              </p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={reports.movementTrend}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 11 }}
                    interval="preserveStartEnd"
                    minTickGap={24}
                  />
                  <YAxis tick={{ fontSize: 12 }} width={36} />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="unitsIn"
                    stroke="var(--chart-2)"
                    strokeWidth={2}
                    dot={false}
                    name="In"
                  />
                  <Line
                    type="monotone"
                    dataKey="unitsOut"
                    stroke="var(--chart-4)"
                    strokeWidth={2}
                    dot={false}
                    name="Out"
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Top sellers</CardTitle>
            <CardDescription>Units sold in the last 30 days.</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            {reports.isLoading ? (
              <Skeleton className="h-full w-full" />
            ) : reports.topSellers.length === 0 ? (
              <p className="flex h-full items-center justify-center text-sm text-muted-foreground">
                No sales in this period yet.
              </p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={reports.topSellers} layout="vertical" margin={{ left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis type="number" tick={{ fontSize: 12 }} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={110}
                    tick={{ fontSize: 11 }}
                  />
                  <Tooltip />
                  <Bar dataKey="units" fill="var(--chart-3)" radius={4} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
