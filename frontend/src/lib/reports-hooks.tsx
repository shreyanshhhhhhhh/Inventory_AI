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
import { formatDate } from "@/lib/format";
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

interface ReportsContextValue {
  movementTrend: MovementTrendPoint[];
  topSellers: TopSellerPoint[];
  stockValue: number;
  openPoValue: number;
  payablesDue: number;
  supplierRows: SupplierPayableRow[];
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

const ReportsContext = createContext<ReportsContextValue | null>(null);

function mapMovementTrend(items: ApiMovementsOverTimePoint[]): MovementTrendPoint[] {
  return items.map((item) => ({
    date: item.date,
    label: formatDate(item.date),
    unitsIn: Number(item.units_in),
    unitsOut: Number(item.units_out),
  }));
}

function mapTopSellers(items: ApiTopSeller[]): TopSellerPoint[] {
  return items.map((item) => ({
    name: item.product_name,
    units: Number(item.units_sold),
  }));
}

function mapSupplierRow(row: ApiAccountsBySupplierRow): SupplierPayableRow {
  return {
    id: `${row.supplier_id}-${row.status}`,
    supplierName: row.supplier_name,
    status: row.status as PurchaseOrder["status"],
    total: Number(row.total),
    purchaseOrderCount: row.purchase_order_count,
  };
}

export function ReportsProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [movementTrend, setMovementTrend] = useState<MovementTrendPoint[]>([]);
  const [topSellers, setTopSellers] = useState<TopSellerPoint[]>([]);
  const [stockValue, setStockValue] = useState(0);
  const [openPoValue, setOpenPoValue] = useState(0);
  const [payablesDue, setPayablesDue] = useState(0);
  const [supplierRows, setSupplierRows] = useState<SupplierPayableRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!isAuthenticated) {
      setMovementTrend([]);
      setTopSellers([]);
      setStockValue(0);
      setOpenPoValue(0);
      setPayablesDue(0);
      setSupplierRows([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const [movements, sellers, summary, bySupplier] = await Promise.all([
        api.insights.movementsOverTime(30),
        api.insights.topSellers(30, 5),
        api.accounts.summary(),
        api.accounts.bySupplier(),
      ]);
      setMovementTrend(mapMovementTrend(movements.items));
      setTopSellers(mapTopSellers(sellers.items));
      setStockValue(Number(summary.stock_value));
      setOpenPoValue(Number(summary.open_po_value));
      setPayablesDue(Number(summary.payables_due));
      setSupplierRows(bySupplier.items.map(mapSupplierRow));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load reports.");
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<ReportsContextValue>(
    () => ({
      movementTrend,
      topSellers,
      stockValue,
      openPoValue,
      payablesDue,
      supplierRows,
      isLoading,
      error,
      refresh,
    }),
    [
      movementTrend,
      topSellers,
      stockValue,
      openPoValue,
      payablesDue,
      supplierRows,
      isLoading,
      error,
      refresh,
    ],
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
