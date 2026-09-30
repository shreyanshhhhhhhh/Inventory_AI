"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type {
  ApiDashboardActivityItem,
  ApiNeedsAttentionItem,
} from "@/lib/api-types";
import { mapApiStockStatus } from "@/lib/stock";

export type DashboardNeedsAttentionItem = {
  id: string;
  productId: string;
  locationId: string;
  sku: string;
  productName: string;
  locationName: string;
  onHand: number;
  reorderPoint: number | null;
  status: ReturnType<typeof mapApiStockStatus>;
};

export type DashboardActivityItem = {
  id: string;
  kind: ApiDashboardActivityItem["kind"];
  occurredAt: string;
  title: string;
  subtitle: string;
  quantity: number | null;
};

interface DashboardContextValue {
  totalStockValue: number;
  lowStockCount: number;
  openPurchaseOrderCount: number;
  pendingApprovals: number;
  openExceptions: number;
  needsAttention: DashboardNeedsAttentionItem[];
  recentActivity: DashboardActivityItem[];
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

function mapNeedsAttention(item: ApiNeedsAttentionItem): DashboardNeedsAttentionItem {
  return {
    id: `${item.product_id}-${item.location_id}`,
    productId: item.product_id,
    locationId: item.location_id,
    sku: item.sku,
    productName: item.product_name,
    locationName: item.location_name,
    onHand: Number(item.on_hand),
    reorderPoint: item.reorder_point === null ? null : Number(item.reorder_point),
    status: mapApiStockStatus(item.status),
  };
}

function mapActivity(item: ApiDashboardActivityItem): DashboardActivityItem {
  return {
    id: item.id,
    kind: item.kind,
    occurredAt: item.occurred_at,
    title: item.title,
    subtitle: item.subtitle,
    quantity: item.quantity === null ? null : Number(item.quantity),
  };
}

export function DashboardProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [totalStockValue, setTotalStockValue] = useState(0);
  const [lowStockCount, setLowStockCount] = useState(0);
  const [openPurchaseOrderCount, setOpenPurchaseOrderCount] = useState(0);
  const [pendingApprovals, setPendingApprovals] = useState(0);
  const [openExceptions, setOpenExceptions] = useState(0);
  const [needsAttention, setNeedsAttention] = useState<DashboardNeedsAttentionItem[]>(
    [],
  );
  const [recentActivity, setRecentActivity] = useState<DashboardActivityItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!isAuthenticated) {
      setTotalStockValue(0);
      setLowStockCount(0);
      setOpenPurchaseOrderCount(0);
      setPendingApprovals(0);
      setOpenExceptions(0);
      setNeedsAttention([]);
      setRecentActivity([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const [summary, attention, activity] = await Promise.all([
        api.dashboard.summary(),
        api.dashboard.needsAttention(),
        api.dashboard.activity(),
      ]);
      setTotalStockValue(Number(summary.total_stock_value));
      setLowStockCount(summary.low_stock_count);
      setOpenPurchaseOrderCount(summary.open_purchase_orders);
      setPendingApprovals(summary.pending_approvals);
      setOpenExceptions(summary.open_exceptions);
      setNeedsAttention(attention.items.map(mapNeedsAttention));
      setRecentActivity(activity.items.map(mapActivity));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load dashboard.");
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<DashboardContextValue>(
    () => ({
      totalStockValue,
      lowStockCount,
      openPurchaseOrderCount,
      pendingApprovals,
      openExceptions,
      needsAttention,
      recentActivity,
      isLoading,
      error,
      refresh,
    }),
    [
      totalStockValue,
      lowStockCount,
      openPurchaseOrderCount,
      pendingApprovals,
      openExceptions,
      needsAttention,
      recentActivity,
      isLoading,
      error,
      refresh,
    ],
  );

  return (
    <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>
  );
}

export function useDashboard(): DashboardContextValue {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error("useDashboard must be used within DashboardProvider");
  }
  return context;
}
