"use client";

import Link from "next/link";
import { AlertTriangle, ClipboardList, PackageOpen, Wallet } from "lucide-react";

import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";
import { StatCard } from "@/components/common/stat-card";
import { StatusBadge } from "@/components/common/status-badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboard } from "@/lib/dashboard-hooks";
import { formatCurrency, formatDateTime } from "@/lib/format";

export function HomePageContent() {
  const {
    totalStockValue,
    unvaluedProductCount,
    lowStockCount,
    openPurchaseOrderCount,
    pendingApprovals,
    needsAttention,
    recentActivity,
    isLoading,
    error,
    refresh,
  } = useDashboard();

  if (isLoading) {
    return (
      <>
        <PageHeader
          title="Home"
          description="A quick read on stock health, purchasing, and recent activity."
        />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-28 w-full" />
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Home"
        description="A quick read on stock health, purchasing, and recent activity."
      />

      {error ? (
        <div className="flex items-center justify-between gap-3 rounded-lg border border-destructive/40 p-3 text-sm text-destructive">
          <span>{error}</span>
          <Button variant="outline" size="sm" onClick={() => void refresh()}>
            Retry
          </Button>
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Total stock value"
          value={formatCurrency(totalStockValue)}
          subtext={
            unvaluedProductCount > 0
              ? `On-hand × preferred supplier cost · ${unvaluedProductCount} product${unvaluedProductCount === 1 ? "" : "s"} without a cost excluded`
              : "On-hand × preferred supplier cost"
          }
          icon={Wallet}
        />
        <StatCard
          label="Items below reorder point"
          value={String(lowStockCount)}
          subtext="Across all locations"
          icon={AlertTriangle}
        />
        <StatCard
          label="Open purchase orders"
          value={String(openPurchaseOrderCount)}
          subtext="Draft, approved, or sent"
          icon={PackageOpen}
        />
        <StatCard
          label="Pending approvals"
          value={String(pendingApprovals)}
          subtext="Agent inbox placeholder"
          icon={ClipboardList}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Needs attention</CardTitle>
            <CardDescription>
              SKUs at or below their reorder point.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {needsAttention.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Everything is above reorder levels.
              </p>
            ) : (
              needsAttention.slice(0, 6).map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2"
                >
                  <div>
                    <p className="text-sm font-medium">{item.productName}</p>
                    <p className="text-xs text-muted-foreground">
                      {item.sku} · {item.locationName} · on hand {item.onHand}
                      {item.reorderPoint !== null
                        ? ` · reorder at ${item.reorderPoint}`
                        : ""}
                    </p>
                  </div>
                  <StatusBadge variant={item.status} />
                </div>
              ))
            )}
            <Link
              href="/inventory"
              className="inline-flex text-sm font-medium text-primary hover:underline"
            >
              View inventory
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
            <CardDescription>
              Latest stock movements and purchase order updates.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {recentActivity.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No recent activity yet.
              </p>
            ) : (
              recentActivity.map((event) => (
                <div
                  key={event.id}
                  className="flex items-start justify-between gap-3 rounded-lg border px-3 py-2"
                >
                  <div>
                    <p className="text-sm font-medium">{event.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {event.subtitle} · {formatDateTime(event.occurredAt)}
                    </p>
                  </div>
                  {event.quantity !== null ? (
                    <span
                      className={
                        event.quantity > 0
                          ? "text-sm font-medium text-emerald-600"
                          : "text-sm font-medium text-red-600"
                      }
                    >
                      {event.quantity > 0
                        ? `+${event.quantity}`
                        : event.quantity}
                    </span>
                  ) : null}
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Pending approvals</CardTitle>
            <CardDescription>Agent suggestions will land here.</CardDescription>
          </CardHeader>
          <CardContent>
            <EmptyState
              icon={ClipboardList}
              title="No pending approvals"
              message="When procurement agents are enabled, proposed purchase orders will appear here for review."
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Open exceptions</CardTitle>
            <CardDescription>Stock and order issues to resolve.</CardDescription>
          </CardHeader>
          <CardContent>
            <EmptyState
              icon={AlertTriangle}
              title="No open exceptions"
              message="Exception handling arrives in a later phase. Overdue POs and stockout risks will show up here."
            />
          </CardContent>
        </Card>
      </div>
    </>
  );
}
