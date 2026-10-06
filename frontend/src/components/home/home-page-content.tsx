"use client";

import Link from "next/link";
import { AlertTriangle, ClipboardList, PackageOpen, Wallet } from "lucide-react";

import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";
import { StatCard } from "@/components/common/stat-card";
import { StatusBadge } from "@/components/common/status-badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboard } from "@/lib/dashboard-hooks";
import { useInboxSuggestions } from "@/lib/chat/suggestions";
import { formatCurrency, formatDateTime } from "@/lib/format";

export function HomePageContent() {
  const {
    totalStockValue,
    lowStockCount,
    openPurchaseOrderCount,
    pendingApprovals,
    needsAttention,
    recentActivity,
    isLoading,
    error,
  } = useDashboard();
  const { items: inboxItems, setStatus } = useInboxSuggestions();
  const pendingInbox = inboxItems.filter((item) => item.status === "pending");

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

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Total stock value"
          value={formatCurrency(totalStockValue)}
          subtext="Based on on-hand × unit cost"
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
          subtext="From Agent Inbox"
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
            {pendingInbox.length === 0 ? (
              <EmptyState
                icon={ClipboardList}
                title="No pending approvals"
                message="Draft POs and emails from Agent Inbox will show up here."
              />
            ) : (
              <div className="space-y-3">
                {pendingInbox.map((item) => (
                  <div key={item.id} className="rounded-lg border px-3 py-2">
                    <p className="text-sm font-medium">{item.title}</p>
                    <p className="text-xs text-muted-foreground">{item.summary}</p>
                    <div className="mt-2 flex gap-2">
                      <button
                        type="button"
                        className="text-xs font-medium text-primary hover:underline"
                        onClick={() => setStatus(item.id, "approved")}
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        className="text-xs font-medium text-muted-foreground hover:underline"
                        onClick={() => setStatus(item.id, "rejected")}
                      >
                        Reject
                      </button>
                    </div>
                  </div>
                ))}
                <Link
                  href="/inbox"
                  className="inline-flex text-sm font-medium text-primary hover:underline"
                >
                  Open Agent Inbox
                </Link>
              </div>
            )}
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
