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

import { mapPurchaseOrder } from "@/lib/api-mappers";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useProducts } from "@/lib/catalog-hooks";
import type { PurchaseOrder, PurchaseOrderStatus } from "@/types";

type PurchaseOrderRow = PurchaseOrder & {
  supplierName: string;
  total: number;
  locationId: string;
};

type TransitionAction = "approve" | "send" | "receive" | "cancel";

interface PurchaseOrdersContextValue {
  purchaseOrders: PurchaseOrderRow[];
  isLoading: boolean;
  error: string | null;
  statusFilter: string;
  supplierFilter: string;
  setStatusFilter: (value: string) => void;
  setSupplierFilter: (value: string) => void;
  refreshPurchaseOrders: () => Promise<void>;
  addPurchaseOrder: (input: {
    supplierId: string;
    expectedDate: string;
    lineItems: Array<{
      productId: string;
      quantity: number;
      unitCost: number;
    }>;
  }) => Promise<PurchaseOrderRow>;
  transitionPurchaseOrder: (
    id: string,
    action: TransitionAction,
  ) => Promise<PurchaseOrderRow>;
  getPurchaseOrderTotal: (order: PurchaseOrder) => number;
  getProductById: (id: string) => ReturnType<typeof useProducts>["products"][number] | undefined;
}

const PurchaseOrdersContext = createContext<PurchaseOrdersContextValue | null>(null);

export function PurchaseOrdersProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const { products } = useProducts();
  const [purchaseOrders, setPurchaseOrders] = useState<PurchaseOrderRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [supplierFilter, setSupplierFilter] = useState("all");

  const refreshPurchaseOrders = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.purchaseOrders.list({
        status: statusFilter === "all" ? undefined : statusFilter,
        supplier_id: supplierFilter === "all" ? undefined : supplierFilter,
        page: 1,
        page_size: 100,
      });
      setPurchaseOrders(response.items.map(mapPurchaseOrder));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load purchase orders.",
      );
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter, supplierFilter]);

  useEffect(() => {
    if (!isAuthenticated) {
      setPurchaseOrders([]);
      setIsLoading(false);
      return;
    }
    const timer = window.setTimeout(() => {
      void refreshPurchaseOrders();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [isAuthenticated, refreshPurchaseOrders]);

  const getProductById = useCallback(
    (id: string) => products.find((product) => product.id === id),
    [products],
  );

  const getPurchaseOrderTotal = useCallback((order: PurchaseOrder) => {
    return order.lineItems.reduce(
      (sum, line) => sum + line.quantity * line.unitCost,
      0,
    );
  }, []);

  const addPurchaseOrder = useCallback(
    async (input: {
      supplierId: string;
      expectedDate: string;
      lineItems: Array<{
        productId: string;
        quantity: number;
        unitCost: number;
      }>;
    }) => {
      const created = mapPurchaseOrder(
        await api.purchaseOrders.create({
          supplier_id: input.supplierId,
          expected_date: input.expectedDate || null,
          line_items: input.lineItems.map((line) => ({
            product_id: line.productId,
            quantity: String(line.quantity),
            unit_cost: line.unitCost > 0 ? line.unitCost.toFixed(2) : null,
          })),
        }),
      );
      await refreshPurchaseOrders();
      return created;
    },
    [refreshPurchaseOrders],
  );

  const transitionPurchaseOrder = useCallback(
    async (id: string, action: TransitionAction) => {
      const updated = mapPurchaseOrder(
        await api.purchaseOrders.transition(id, { action }),
      );
      setPurchaseOrders((current) =>
        current.map((order) => (order.id === id ? updated : order)),
      );
      return updated;
    },
    [],
  );

  const value = useMemo<PurchaseOrdersContextValue>(
    () => ({
      purchaseOrders,
      isLoading,
      error,
      statusFilter,
      supplierFilter,
      setStatusFilter,
      setSupplierFilter,
      refreshPurchaseOrders,
      addPurchaseOrder,
      transitionPurchaseOrder,
      getPurchaseOrderTotal,
      getProductById,
    }),
    [
      purchaseOrders,
      isLoading,
      error,
      statusFilter,
      supplierFilter,
      refreshPurchaseOrders,
      addPurchaseOrder,
      transitionPurchaseOrder,
      getPurchaseOrderTotal,
      getProductById,
    ],
  );

  return (
    <PurchaseOrdersContext.Provider value={value}>
      {children}
    </PurchaseOrdersContext.Provider>
  );
}

export function usePurchaseOrders(): PurchaseOrdersContextValue {
  const context = useContext(PurchaseOrdersContext);
  if (!context) {
    throw new Error("usePurchaseOrders must be used within PurchaseOrdersProvider");
  }
  return context;
}

export type { TransitionAction, PurchaseOrderStatus };
