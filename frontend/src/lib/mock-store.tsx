"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  MOCK_BUSINESS,
  MOCK_CURRENT_USER,
  MOCK_LOCATIONS,
  MOCK_MOVEMENTS,
  MOCK_PRODUCTS,
  MOCK_PURCHASE_ORDERS,
  MOCK_STOCK_LEVELS,
  MOCK_SUPPLIERS,
  MOCK_TEAM_USERS,
} from "@/lib/mock-data";
import type {
  BusinessProfile,
  Location,
  Product,
  PurchaseOrder,
  PurchaseOrderStatus,
  StockLevel,
  StockMovement,
  StockStatus,
  Supplier,
  TeamUser,
} from "@/types";

function newId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

function poTotal(order: PurchaseOrder): number {
  return order.lineItems.reduce(
    (sum, line) => sum + line.quantity * line.unitCost,
    0,
  );
}

function getStockStatus(onHand: number, reorderPoint: number): StockStatus {
  if (onHand <= 0) return "out";
  if (onHand <= reorderPoint) return "low";
  return "in-stock";
}

interface MockStoreValue {
  business: BusinessProfile;
  currentUser: typeof MOCK_CURRENT_USER;
  locations: Location[];
  products: Product[];
  suppliers: Supplier[];
  stockLevels: StockLevel[];
  movements: StockMovement[];
  purchaseOrders: PurchaseOrder[];
  teamUsers: TeamUser[];
  getProductById: (id: string) => Product | undefined;
  getSupplierById: (id: string) => Supplier | undefined;
  getLocationById: (id: string) => Location | undefined;
  getStockLevel: (productId: string, locationId: string) => number;
  getProductStockStatus: (productId: string) => StockStatus;
  getPurchaseOrderTotal: (order: PurchaseOrder) => number;
  addProduct: (product: Omit<Product, "id">) => Product;
  updateProduct: (id: string, product: Omit<Product, "id">) => void;
  deleteProduct: (id: string) => void;
  addSupplier: (supplier: Omit<Supplier, "id">) => Supplier;
  updateSupplier: (id: string, supplier: Omit<Supplier, "id">) => void;
  recordMovement: (input: {
    productId: string;
    locationId: string;
    type: StockMovement["type"];
    quantity: number;
    note: string;
  }) => void;
  addPurchaseOrder: (input: {
    supplierId: string;
    expectedDate: string;
    lineItems: Array<{ productId: string; quantity: number; unitCost: number }>;
  }) => PurchaseOrder;
  updatePurchaseOrderStatus: (
    id: string,
    status: PurchaseOrderStatus,
  ) => void;
  updateBusiness: (business: BusinessProfile) => void;
  updateLocations: (locations: Location[]) => void;
}

const MockStoreContext = createContext<MockStoreValue | null>(null);

export function MockStoreProvider({ children }: { children: ReactNode }) {
  const [business, setBusiness] = useState(MOCK_BUSINESS);
  const [products, setProducts] = useState(MOCK_PRODUCTS);
  const [suppliers, setSuppliers] = useState(MOCK_SUPPLIERS);
  const [locations, setLocations] = useState(MOCK_LOCATIONS);
  const [stockLevels, setStockLevels] = useState(MOCK_STOCK_LEVELS);
  const [movements, setMovements] = useState(MOCK_MOVEMENTS);
  const [purchaseOrders, setPurchaseOrders] = useState(MOCK_PURCHASE_ORDERS);

  const getProductById = useCallback(
    (id: string) => products.find((product) => product.id === id),
    [products],
  );

  const getSupplierById = useCallback(
    (id: string) => suppliers.find((supplier) => supplier.id === id),
    [suppliers],
  );

  const getLocationById = useCallback(
    (id: string) => locations.find((location) => location.id === id),
    [locations],
  );

  const getStockLevel = useCallback(
    (productId: string, locationId: string) =>
      stockLevels.find(
        (level) =>
          level.productId === productId && level.locationId === locationId,
      )?.onHand ?? 0,
    [stockLevels],
  );

  const getProductStockStatus = useCallback(
    (productId: string): StockStatus => {
      const product = products.find((item) => item.id === productId);
      if (!product) return "out";
      const onHand = stockLevels
        .filter((level) => level.productId === productId)
        .reduce((sum, level) => sum + level.onHand, 0);
      return getStockStatus(onHand, product.reorderPoint);
    },
    [products, stockLevels],
  );

  const addProduct = useCallback((product: Omit<Product, "id">) => {
    const created: Product = {
      ...product,
      id: newId("p"),
      categoryName: product.categoryName,
      preferredSupplierName: product.preferredSupplierName,
      isActive: true,
    };
    setProducts((current) => [...current, created]);
    setStockLevels((current) => [
      ...current,
      { productId: created.id, locationId: "loc-1", onHand: 0 },
    ]);
    return created;
  }, []);

  const updateProduct = useCallback(
    (id: string, product: Omit<Product, "id">) => {
      setProducts((current) =>
        current.map((item) => (item.id === id ? { ...product, id } : item)),
      );
    },
    [],
  );

  const deleteProduct = useCallback((id: string) => {
    setProducts((current) => current.filter((item) => item.id !== id));
  }, []);

  const addSupplier = useCallback((supplier: Omit<Supplier, "id">) => {
    const created: Supplier = { ...supplier, id: newId("sup"), isActive: true };
    setSuppliers((current) => [...current, created]);
    return created;
  }, []);

  const updateSupplier = useCallback(
    (id: string, supplier: Omit<Supplier, "id">) => {
      setSuppliers((current) =>
        current.map((item) => (item.id === id ? { ...supplier, id } : item)),
      );
    },
    [],
  );

  const recordMovement = useCallback(
    (input: {
      productId: string;
      locationId: string;
      type: StockMovement["type"];
      quantity: number;
      note: string;
    }) => {
      const signedQuantity =
        input.type === "sale"
          ? -Math.abs(input.quantity)
          : input.type === "receipt"
            ? Math.abs(input.quantity)
            : input.quantity;

      const currentOnHand =
        stockLevels.find(
          (level) =>
            level.productId === input.productId &&
            level.locationId === input.locationId,
        )?.onHand ?? 0;

      if (
        input.type !== "adjustment" &&
        currentOnHand + signedQuantity < 0
      ) {
        throw new Error("This movement would make stock negative.");
      }

      if (input.type === "adjustment" && !input.note.trim()) {
        throw new Error("Adjustments require a note.");
      }

      const movement: StockMovement = {
        id: newId("m"),
        date: new Date().toISOString(),
        productId: input.productId,
        locationId: input.locationId,
        type: input.type,
        quantity: signedQuantity,
        userId: MOCK_CURRENT_USER.id,
        note: input.note,
      };

      setMovements((current) => [movement, ...current]);
      setStockLevels((current) => {
        const existing = current.find(
          (level) =>
            level.productId === input.productId &&
            level.locationId === input.locationId,
        );
        if (existing) {
          return current.map((level) =>
            level.productId === input.productId &&
            level.locationId === input.locationId
              ? { ...level, onHand: level.onHand + signedQuantity }
              : level,
          );
        }
        return [
          ...current,
          {
            productId: input.productId,
            locationId: input.locationId,
            onHand: signedQuantity,
          },
        ];
      });
    },
    [stockLevels],
  );

  const addPurchaseOrder = useCallback(
    (input: {
      supplierId: string;
      expectedDate: string;
      lineItems: Array<{
        productId: string;
        quantity: number;
        unitCost: number;
      }>;
    }) => {
      const nextNumber = purchaseOrders.length + 1;
      const created: PurchaseOrder = {
        id: newId("po"),
        poNumber: `PO-2026-${String(nextNumber).padStart(3, "0")}`,
        supplierId: input.supplierId,
        status: "draft",
        expectedDate: input.expectedDate,
        lineItems: input.lineItems.map((line) => ({
          ...line,
          id: newId("pol"),
        })),
      };
      setPurchaseOrders((current) => [created, ...current]);
      return created;
    },
    [purchaseOrders.length],
  );

  const updatePurchaseOrderStatus = useCallback(
    (id: string, status: PurchaseOrderStatus) => {
      setPurchaseOrders((current) =>
        current.map((order) =>
          order.id === id ? { ...order, status } : order,
        ),
      );
    },
    [],
  );

  const value = useMemo<MockStoreValue>(
    () => ({
      business,
      currentUser: MOCK_CURRENT_USER,
      locations,
      products,
      suppliers,
      stockLevels,
      movements,
      purchaseOrders,
      teamUsers: MOCK_TEAM_USERS,
      getProductById,
      getSupplierById,
      getLocationById,
      getStockLevel,
      getProductStockStatus,
      getPurchaseOrderTotal: poTotal,
      addProduct,
      updateProduct,
      deleteProduct,
      addSupplier,
      updateSupplier,
      recordMovement,
      addPurchaseOrder,
      updatePurchaseOrderStatus,
      updateBusiness: setBusiness,
      updateLocations: setLocations,
    }),
    [
      business,
      locations,
      products,
      suppliers,
      stockLevels,
      movements,
      purchaseOrders,
      getProductById,
      getSupplierById,
      getLocationById,
      getStockLevel,
      getProductStockStatus,
      addProduct,
      updateProduct,
      deleteProduct,
      addSupplier,
      updateSupplier,
      recordMovement,
      addPurchaseOrder,
      updatePurchaseOrderStatus,
    ],
  );

  return (
    <MockStoreContext.Provider value={value}>
      {children}
    </MockStoreContext.Provider>
  );
}

export function useMockStore(): MockStoreValue {
  const context = useContext(MockStoreContext);
  if (!context) {
    throw new Error("useMockStore must be used within MockStoreProvider");
  }
  return context;
}

export function useInventory() {
  const {
    products,
    locations,
    stockLevels,
    movements,
    getStockLevel,
    getProductById,
    getLocationById,
    recordMovement,
  } = useMockStore();
  return {
    products,
    locations,
    stockLevels,
    movements,
    getStockLevel,
    getProductById,
    getLocationById,
    recordMovement,
  };
}

export function usePurchaseOrders() {
  const {
    purchaseOrders,
    addPurchaseOrder,
    updatePurchaseOrderStatus,
    getPurchaseOrderTotal,
    getSupplierById,
    getProductById,
  } = useMockStore();
  return {
    purchaseOrders,
    addPurchaseOrder,
    updatePurchaseOrderStatus,
    getPurchaseOrderTotal,
    getSupplierById,
    getProductById,
  };
}

export function useDashboard() {
  const {
    products,
    stockLevels,
    purchaseOrders,
    movements,
    getProductById,
    getPurchaseOrderTotal,
  } = useMockStore();

  const totalStockValue = useMemo(() => {
    return stockLevels.reduce((sum, level) => {
      const product = getProductById(level.productId);
      if (!product) return sum;
      return sum + level.onHand * product.cost;
    }, 0);
  }, [stockLevels, getProductById]);

  const itemsBelowReorder = useMemo(() => {
    return products.filter((product) => {
      const onHand = stockLevels
        .filter((level) => level.productId === product.id)
        .reduce((sum, level) => sum + level.onHand, 0);
      return onHand <= product.reorderPoint;
    });
  }, [products, stockLevels]);

  const openPurchaseOrders = useMemo(
    () =>
      purchaseOrders.filter((order) =>
        ["draft", "approved", "sent"].includes(order.status),
      ),
    [purchaseOrders],
  );

  return {
    totalStockValue,
    itemsBelowReorder,
    openPurchaseOrders,
    pendingApprovals: 3,
    recentMovements: movements.slice(0, 8),
    getProductById,
    getPurchaseOrderTotal,
  };
}

export { getStockStatus };
