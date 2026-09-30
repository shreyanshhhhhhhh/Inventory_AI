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

import { mapLocation, mapMovement, mapStockLevel } from "@/lib/api-mappers";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useProducts } from "@/lib/catalog-hooks";
import type { Location, MovementType, StockLevel, StockMovement } from "@/types";

type StockRow = StockLevel & {
  sku: string;
  productName: string;
  locationName: string;
  reorderPoint: number;
  status: "in_stock" | "low" | "out";
};

type MovementRow = StockMovement & {
  productName: string;
  locationName: string;
  userName: string;
};

interface InventoryContextValue {
  products: ReturnType<typeof useProducts>["products"];
  locations: Location[];
  stockLevels: StockRow[];
  movements: MovementRow[];
  stockLoading: boolean;
  movementsLoading: boolean;
  stockError: string | null;
  movementsError: string | null;
  stockSearch: string;
  locationFilter: string;
  lowStockOnly: boolean;
  movementTypeFilter: string;
  setStockSearch: (value: string) => void;
  setLocationFilter: (value: string) => void;
  setLowStockOnly: (value: boolean) => void;
  setMovementTypeFilter: (value: string) => void;
  refreshStock: () => Promise<void>;
  refreshMovements: () => Promise<void>;
  getStockLevel: (productId: string, locationId: string) => StockLevel | undefined;
  getProductById: (id: string) => ReturnType<typeof useProducts>["products"][number] | undefined;
  getLocationById: (id: string) => Location | undefined;
  recordMovement: (input: {
    productId: string;
    locationId: string;
    type: MovementType;
    quantity: number;
    note: string;
  }) => Promise<void>;
}

const InventoryContext = createContext<InventoryContextValue | null>(null);

export function InventoryProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const { products } = useProducts();

  const [locations, setLocations] = useState<Location[]>([]);
  const [stockLevels, setStockLevels] = useState<StockRow[]>([]);
  const [movements, setMovements] = useState<MovementRow[]>([]);
  const [stockLoading, setStockLoading] = useState(true);
  const [movementsLoading, setMovementsLoading] = useState(true);
  const [stockError, setStockError] = useState<string | null>(null);
  const [movementsError, setMovementsError] = useState<string | null>(null);
  const [stockSearch, setStockSearch] = useState("");
  const [locationFilter, setLocationFilter] = useState("all");
  const [lowStockOnly, setLowStockOnly] = useState(false);
  const [movementTypeFilter, setMovementTypeFilter] = useState("all");

  const refreshLocations = useCallback(async () => {
    const response = await api.inventory.locations();
    setLocations(response.map(mapLocation));
  }, []);

  const refreshStock = useCallback(async () => {
    setStockLoading(true);
    setStockError(null);
    try {
      const response = await api.inventory.stock({
        search: stockSearch.trim() || undefined,
        location_id: locationFilter === "all" ? undefined : locationFilter,
        low_only: lowStockOnly,
        page: 1,
        page_size: 100,
      });
      setStockLevels(response.items.map(mapStockLevel));
    } catch (error) {
      setStockError(
        error instanceof Error ? error.message : "Could not load stock levels.",
      );
    } finally {
      setStockLoading(false);
    }
  }, [stockSearch, locationFilter, lowStockOnly]);

  const refreshMovements = useCallback(async () => {
    setMovementsLoading(true);
    setMovementsError(null);
    try {
      const response = await api.inventory.movements({
        type: movementTypeFilter === "all" ? undefined : movementTypeFilter,
        page: 1,
        page_size: 100,
      });
      setMovements(response.items.map(mapMovement));
    } catch (error) {
      setMovementsError(
        error instanceof Error ? error.message : "Could not load movements.",
      );
    } finally {
      setMovementsLoading(false);
    }
  }, [movementTypeFilter]);

  useEffect(() => {
    if (!isAuthenticated) {
      setLocations([]);
      setStockLevels([]);
      setMovements([]);
      setStockLoading(false);
      setMovementsLoading(false);
      return;
    }
    const timer = window.setTimeout(() => {
      void refreshLocations();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [isAuthenticated, refreshLocations]);

  useEffect(() => {
    if (!isAuthenticated) return;
    const timer = window.setTimeout(() => {
      void refreshStock();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [isAuthenticated, refreshStock]);

  useEffect(() => {
    if (!isAuthenticated) return;
    const timer = window.setTimeout(() => {
      void refreshMovements();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [isAuthenticated, refreshMovements]);

  const getProductById = useCallback(
    (id: string) => products.find((product) => product.id === id),
    [products],
  );

  const getLocationById = useCallback(
    (id: string) => locations.find((location) => location.id === id),
    [locations],
  );

  const getStockLevel = useCallback(
    (productId: string, locationId: string) =>
      stockLevels.find(
        (level) => level.productId === productId && level.locationId === locationId,
      ),
    [stockLevels],
  );

  const recordMovement = useCallback(
    async (input: {
      productId: string;
      locationId: string;
      type: MovementType;
      quantity: number;
      note: string;
    }) => {
      const quantityText =
        input.type === "adjustment"
          ? String(input.quantity)
          : String(Math.abs(input.quantity));

      await api.inventory.recordMovement({
        product_id: input.productId,
        location_id: input.locationId,
        type: input.type,
        quantity: quantityText,
        note: input.note.trim() || null,
      });
      await Promise.all([refreshStock(), refreshMovements()]);
    },
    [refreshStock, refreshMovements],
  );

  const value = useMemo<InventoryContextValue>(
    () => ({
      products,
      locations,
      stockLevels,
      movements,
      stockLoading,
      movementsLoading,
      stockError,
      movementsError,
      stockSearch,
      locationFilter,
      lowStockOnly,
      movementTypeFilter,
      setStockSearch,
      setLocationFilter,
      setLowStockOnly,
      setMovementTypeFilter,
      refreshStock,
      refreshMovements,
      getStockLevel,
      getProductById,
      getLocationById,
      recordMovement,
    }),
    [
      products,
      locations,
      stockLevels,
      movements,
      stockLoading,
      movementsLoading,
      stockError,
      movementsError,
      stockSearch,
      locationFilter,
      lowStockOnly,
      movementTypeFilter,
      refreshStock,
      refreshMovements,
      getStockLevel,
      getProductById,
      getLocationById,
      recordMovement,
    ],
  );

  return (
    <InventoryContext.Provider value={value}>{children}</InventoryContext.Provider>
  );
}

export function useInventory(): InventoryContextValue {
  const context = useContext(InventoryContext);
  if (!context) {
    throw new Error("useInventory must be used within InventoryProvider");
  }
  return context;
}
