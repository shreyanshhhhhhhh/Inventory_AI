"use client";

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

import { PageHeader } from "@/components/common/page-header";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useReports } from "@/lib/reports-hooks";

export function InsightsPageContent() {
  const { movementTrend, topSellers, isLoading, error } = useReports();

  if (isLoading) {
    return (
      <>
        <PageHeader
          title="Insights"
          description="Charts from sales and movement history. Forecasting arrives in Phase 2."
        />
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-80 w-full" />
          <Skeleton className="h-80 w-full" />
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Insights"
        description="Charts from sales and movement history. Forecasting arrives in Phase 2."
      />

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Stock movements over time</CardTitle>
            <CardDescription>
              Daily receipt and sale units for the last 30 days.
            </CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            {movementTrend.every((point) => point.unitsIn === 0 && point.unitsOut === 0) ? (
              <p className="flex h-full items-center justify-center text-sm text-muted-foreground">
                No movement history in this period yet.
              </p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={movementTrend}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 11 }}
                    interval="preserveStartEnd"
                    minTickGap={24}
                  />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="unitsIn"
                    stroke="var(--chart-2)"
                    strokeWidth={2}
                    name="In"
                  />
                  <Line
                    type="monotone"
                    dataKey="unitsOut"
                    stroke="var(--chart-4)"
                    strokeWidth={2}
                    name="Out"
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Top 5 sellers</CardTitle>
            <CardDescription>Units sold in the last 30 days.</CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            {topSellers.length === 0 ? (
              <p className="flex h-full items-center justify-center text-sm text-muted-foreground">
                No sales in this period yet.
              </p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={topSellers} layout="vertical" margin={{ left: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis type="number" tick={{ fontSize: 12 }} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={120}
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

      <Card>
        <CardHeader>
          <CardTitle>Ask why</CardTitle>
          <CardDescription>
            Natural-language explanations are not available in Phase 1.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row">
          <Input disabled placeholder="Why is spinach low this week?" />
          <Button disabled>Coming soon</Button>
        </CardContent>
      </Card>
    </>
  );
}
