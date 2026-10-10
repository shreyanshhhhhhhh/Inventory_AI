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
import { parseDecimal } from "@/lib/decimal";
import type { LoadResult } from "@/lib/load-result";
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

type DashboardData = {
  totalStockValue: number;
  unvaluedProductCount: number;
  lowStockCount: number;
  openPurchaseOrderCount: number;
  pendingApprovals: number;
  openExceptions: number;
  needsAttention: DashboardNeedsAttentionItem[];
  recentActivity: DashboardActivityItem[];
};

interface DashboardContextValue extends DashboardData {
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

const EMPTY_DASHBOARD: DashboardData = {
  totalStockValue: 0,
  unvaluedProductCount: 0,
  lowStockCount: 0,
  openPurchaseOrderCount: 0,
  pendingApprovals: 0,
  openExceptions: 0,
  needsAttention: [],
  recentActivity: [],
};

const DashboardContext = createContext<DashboardContextValue | null>(null);

function mapNeedsAttention(item: ApiNeedsAttentionItem): DashboardNeedsAttentionItem {
  return {
    id: `${item.product_id}-${item.location_id}`,
    productId: item.product_id,
    locationId: item.location_id,
    sku: item.sku,
    productName: item.product_name,
    locationName: item.location_name,
    onHand: parseDecimal(item.on_hand),
    reorderPoint: item.reorder_point === null ? null : parseDecimal(item.reorder_point),
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
    quantity: item.quantity === null ? null : parseDecimal(item.quantity),
  };
}

async function fetchDashboard(): Promise<LoadResult<DashboardData>> {
  try {
    const [summary, attention, activity] = await Promise.all([
      api.dashboard.summary(),
      api.dashboard.needsAttention(),
      api.dashboard.activity(),
    ]);
    return {
      data: {
        totalStockValue: parseDecimal(summary.total_stock_value),
        unvaluedProductCount: summary.unvalued_product_count,
        lowStockCount: summary.low_stock_count,
        openPurchaseOrderCount: summary.open_purchase_orders,
        pendingApprovals: summary.pending_approvals,
        openExceptions: summary.open_exceptions,
        needsAttention: attention.items.map(mapNeedsAttention),
        recentActivity: activity.items.map(mapActivity),
      },
      error: null,
    };
  } catch (err) {
    return {
      data: null,
      error: err instanceof Error ? err.message : "Could not load dashboard.",
    };
  }
}

export function DashboardProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated, isOnboarded } = useAuth();
  const ready = isAuthenticated && isOnboarded;
  const [data, setData] = useState<DashboardData>(EMPTY_DASHBOARD);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const apply = useCallback((result: LoadResult<DashboardData>) => {
    if (result.data) setData(result.data);
    setError(result.error);
    setIsLoading(false);
  }, []);

  const refresh = useCallback(async () => {
    if (!ready) return;
    setIsLoading(true);
    apply(await fetchDashboard());
  }, [ready, apply]);

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    void fetchDashboard().then((result) => {
      if (!cancelled) apply(result);
    });
    return () => {
      cancelled = true;
    };
  }, [ready, apply]);

  const value = useMemo<DashboardContextValue>(
    () => ({
      ...(ready ? data : EMPTY_DASHBOARD),
      isLoading: ready && isLoading,
      error: ready ? error : null,
      refresh,
    }),
    [ready, data, isLoading, error, refresh],
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
