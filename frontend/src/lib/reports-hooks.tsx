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
  ApiAccountsBySupplierRow,
  ApiMovementsOverTimePoint,
  ApiTopSeller,
} from "@/lib/api-types";
import { parseDecimal } from "@/lib/decimal";
import { formatDate } from "@/lib/format";
import type { LoadResult } from "@/lib/load-result";
import type { PurchaseOrder } from "@/types";

export type MovementTrendPoint = {
  date: string;
  label: string;
  unitsIn: number;
  unitsOut: number;
};

export type TopSellerPoint = {
  name: string;
  units: number;
};

export type SupplierPayableRow = {
  id: string;
  supplierName: string;
  status: PurchaseOrder["status"];
  total: number;
  purchaseOrderCount: number;
};

type ReportsData = {
  movementTrend: MovementTrendPoint[];
  topSellers: TopSellerPoint[];
  stockValue: number;
  unvaluedProductCount: number;
  openPoValue: number;
  payablesDue: number;
  supplierRows: SupplierPayableRow[];
};

interface ReportsContextValue extends ReportsData {
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

const EMPTY_REPORTS: ReportsData = {
  movementTrend: [],
  topSellers: [],
  stockValue: 0,
  unvaluedProductCount: 0,
  openPoValue: 0,
  payablesDue: 0,
  supplierRows: [],
};

const ReportsContext = createContext<ReportsContextValue | null>(null);

function mapMovementTrend(items: ApiMovementsOverTimePoint[]): MovementTrendPoint[] {
  return items.map((item) => ({
    date: item.date,
    label: formatDate(item.date),
    unitsIn: parseDecimal(item.units_in),
    unitsOut: parseDecimal(item.units_out),
  }));
}

function mapTopSellers(items: ApiTopSeller[]): TopSellerPoint[] {
  return items.map((item) => ({
    name: item.product_name,
    units: parseDecimal(item.units_sold),
  }));
}

function mapSupplierRow(row: ApiAccountsBySupplierRow): SupplierPayableRow {
  return {
    id: `${row.supplier_id}-${row.status}`,
    supplierName: row.supplier_name,
    status: row.status as PurchaseOrder["status"],
    total: parseDecimal(row.total),
    purchaseOrderCount: row.purchase_order_count,
  };
}

async function fetchReports(): Promise<LoadResult<ReportsData>> {
  try {
    const [movements, sellers, summary, bySupplier] = await Promise.all([
      api.insights.movementsOverTime(30),
      api.insights.topSellers(30, 5),
      api.accounts.summary(),
      api.accounts.bySupplier(),
    ]);
    return {
      data: {
        movementTrend: mapMovementTrend(movements.items),
        topSellers: mapTopSellers(sellers.items),
        stockValue: parseDecimal(summary.stock_value),
        unvaluedProductCount: summary.unvalued_product_count,
        openPoValue: parseDecimal(summary.open_po_value),
        payablesDue: parseDecimal(summary.payables_due),
        supplierRows: bySupplier.items.map(mapSupplierRow),
      },
      error: null,
    };
  } catch (err) {
    return {
      data: null,
      error: err instanceof Error ? err.message : "Could not load reports.",
    };
  }
}

export function ReportsProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated, isOnboarded } = useAuth();
  const ready = isAuthenticated && isOnboarded;
  const [data, setData] = useState<ReportsData>(EMPTY_REPORTS);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const apply = useCallback((result: LoadResult<ReportsData>) => {
    if (result.data) setData(result.data);
    setError(result.error);
    setIsLoading(false);
  }, []);

  const refresh = useCallback(async () => {
    if (!ready) return;
    setIsLoading(true);
    apply(await fetchReports());
  }, [ready, apply]);

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    void fetchReports().then((result) => {
      if (!cancelled) apply(result);
    });
    return () => {
      cancelled = true;
    };
  }, [ready, apply]);

  const value = useMemo<ReportsContextValue>(
    () => ({
      ...(ready ? data : EMPTY_REPORTS),
      isLoading: ready && isLoading,
      error: ready ? error : null,
      refresh,
    }),
    [ready, data, isLoading, error, refresh],
  );

  return (
    <ReportsContext.Provider value={value}>{children}</ReportsContext.Provider>
  );
}

export function useReports(): ReportsContextValue {
  const context = useContext(ReportsContext);
  if (!context) {
    throw new Error("useReports must be used within ReportsProvider");
  }
  return context;
}
