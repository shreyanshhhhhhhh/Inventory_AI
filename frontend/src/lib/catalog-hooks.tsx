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

import {
  mapCategory,
  mapProduct,
  mapProductWrite,
  mapSupplier,
  mapSupplierWrite,
} from "@/lib/api-mappers";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { Category, Product, Supplier } from "@/types";

type ProductWrite = Omit<Product, "id" | "categoryName" | "preferredSupplierName">;

interface CatalogContextValue {
  products: Product[];
  productsTotal: number;
  productsPage: number;
  productsPageSize: number;
  productsLoading: boolean;
  productsError: string | null;
  productSearch: string;
  productCategoryFilter: string;
  setProductSearch: (value: string) => void;
  setProductCategoryFilter: (value: string) => void;
  setProductsPage: (page: number) => void;
  refreshProducts: () => Promise<void>;
  addProduct: (product: ProductWrite) => Promise<Product>;
  updateProduct: (id: string, product: ProductWrite) => Promise<void>;
  deleteProduct: (id: string) => Promise<void>;
  categories: Category[];
  categoriesLoading: boolean;
  addCategory: (name: string) => Promise<Category>;
  suppliers: Supplier[];
  suppliersLoading: boolean;
  suppliersError: string | null;
  refreshSuppliers: () => Promise<void>;
  addSupplier: (supplier: Omit<Supplier, "id" | "isActive">) => Promise<Supplier>;
  updateSupplier: (
    id: string,
    supplier: Omit<Supplier, "id" | "isActive">,
  ) => Promise<void>;
  getSupplierById: (id: string) => Supplier | undefined;
}

const CatalogContext = createContext<CatalogContextValue | null>(null);

export function CatalogProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [products, setProducts] = useState<Product[]>([]);
  const [productsTotal, setProductsTotal] = useState(0);
  const [productsPage, setProductsPage] = useState(1);
  const [productsPageSize] = useState(10);
  const [productsLoading, setProductsLoading] = useState(true);
  const [productsError, setProductsError] = useState<string | null>(null);
  const [productSearch, setProductSearch] = useState("");
  const [productCategoryFilter, setProductCategoryFilter] = useState("all");

  const [categories, setCategories] = useState<Category[]>([]);
  const [categoriesLoading, setCategoriesLoading] = useState(true);

  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [suppliersLoading, setSuppliersLoading] = useState(true);
  const [suppliersError, setSuppliersError] = useState<string | null>(null);

  const refreshProducts = useCallback(async () => {
    setProductsLoading(true);
    setProductsError(null);
    try {
      const response = await api.products.list({
        search: productSearch.trim() || undefined,
        category_id:
          productCategoryFilter === "all" ? undefined : productCategoryFilter,
        page: productsPage,
        page_size: productsPageSize,
      });
      setProducts(response.items.map(mapProduct));
      setProductsTotal(response.total);
    } catch (error) {
      setProductsError(
        error instanceof Error ? error.message : "Could not load products.",
      );
    } finally {
      setProductsLoading(false);
    }
  }, [productSearch, productCategoryFilter, productsPage, productsPageSize]);

  const refreshCategories = useCallback(async () => {
    setCategoriesLoading(true);
    try {
      const response = await api.categories.list();
      setCategories(response.map(mapCategory));
    } finally {
      setCategoriesLoading(false);
    }
  }, []);

  const refreshSuppliers = useCallback(async () => {
    setSuppliersLoading(true);
    setSuppliersError(null);
    try {
      const response = await api.suppliers.list();
      setSuppliers(response.map(mapSupplier));
    } catch (error) {
      setSuppliersError(
        error instanceof Error ? error.message : "Could not load suppliers.",
      );
    } finally {
      setSuppliersLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated) {
      setProducts([]);
      setProductsTotal(0);
      setProductsLoading(false);
      setProductsError(null);
      return;
    }
    const timer = window.setTimeout(() => {
      void refreshProducts();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [isAuthenticated, refreshProducts]);

  useEffect(() => {
    if (!isAuthenticated) {
      setCategories([]);
      setCategoriesLoading(false);
      setSuppliers([]);
      setSuppliersLoading(false);
      setSuppliersError(null);
      return;
    }
    const timer = window.setTimeout(() => {
      void refreshCategories();
      void refreshSuppliers();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [isAuthenticated, refreshCategories, refreshSuppliers]);

  const addCategory = useCallback(async (name: string) => {
    const created = mapCategory(await api.categories.create(name));
    setCategories((current) =>
      [...current, created].sort((a, b) => a.name.localeCompare(b.name)),
    );
    return created;
  }, []);

  const addProduct = useCallback(
    async (product: ProductWrite) => {
      const created = mapProduct(
        await api.products.create(mapProductWrite(product)),
      );
      await refreshProducts();
      return created;
    },
    [refreshProducts],
  );

  const updateProduct = useCallback(
    async (id: string, product: ProductWrite) => {
      await api.products.update(id, mapProductWrite(product));
      await refreshProducts();
    },
    [refreshProducts],
  );

  const deleteProduct = useCallback(
    async (id: string) => {
      await api.products.archive(id);
      await refreshProducts();
    },
    [refreshProducts],
  );

  const addSupplier = useCallback(
    async (supplier: Omit<Supplier, "id" | "isActive">) => {
      const created = mapSupplier(
        await api.suppliers.create(mapSupplierWrite(supplier)),
      );
      setSuppliers((current) =>
        [...current, created].sort((a, b) => a.name.localeCompare(b.name)),
      );
      return created;
    },
    [],
  );

  const updateSupplier = useCallback(
    async (id: string, supplier: Omit<Supplier, "id" | "isActive">) => {
      const updated = mapSupplier(
        await api.suppliers.update(id, mapSupplierWrite(supplier)),
      );
      setSuppliers((current) =>
        current.map((item) => (item.id === id ? updated : item)),
      );
    },
    [],
  );

  const getSupplierById = useCallback(
    (id: string) => suppliers.find((supplier) => supplier.id === id),
    [suppliers],
  );

  const value = useMemo<CatalogContextValue>(
    () => ({
      products,
      productsTotal,
      productsPage,
      productsPageSize,
      productsLoading,
      productsError,
      productSearch,
      productCategoryFilter,
      setProductSearch,
      setProductCategoryFilter,
      setProductsPage,
      refreshProducts,
      addProduct,
      updateProduct,
      deleteProduct,
      categories,
      categoriesLoading,
      addCategory,
      suppliers,
      suppliersLoading,
      suppliersError,
      refreshSuppliers,
      addSupplier,
      updateSupplier,
      getSupplierById,
    }),
    [
      products,
      productsTotal,
      productsPage,
      productsPageSize,
      productsLoading,
      productsError,
      productSearch,
      productCategoryFilter,
      refreshProducts,
      addProduct,
      updateProduct,
      deleteProduct,
      categories,
      categoriesLoading,
      addCategory,
      suppliers,
      suppliersLoading,
      suppliersError,
      refreshSuppliers,
      addSupplier,
      updateSupplier,
      getSupplierById,
    ],
  );

  return (
    <CatalogContext.Provider value={value}>{children}</CatalogContext.Provider>
  );
}

function useCatalogContext(): CatalogContextValue {
  const context = useContext(CatalogContext);
  if (!context) {
    throw new Error("Catalog hooks must be used within CatalogProvider");
  }
  return context;
}

export function useProducts() {
  const {
    products,
    productsTotal,
    productsPage,
    productsPageSize,
    productsLoading,
    productsError,
    productSearch,
    productCategoryFilter,
    setProductSearch,
    setProductCategoryFilter,
    setProductsPage,
    refreshProducts,
    addProduct,
    updateProduct,
    deleteProduct,
  } = useCatalogContext();

  return {
    products,
    total: productsTotal,
    page: productsPage,
    pageSize: productsPageSize,
    isLoading: productsLoading,
    error: productsError,
    search: productSearch,
    categoryFilter: productCategoryFilter,
    setSearch: setProductSearch,
    setCategoryFilter: setProductCategoryFilter,
    setPage: setProductsPage,
    refresh: refreshProducts,
    addProduct,
    updateProduct,
    deleteProduct,
  };
}

export function useCategories() {
  const { categories, categoriesLoading, addCategory } = useCatalogContext();
  return { categories, isLoading: categoriesLoading, addCategory };
}

export function useSuppliers() {
  const {
    suppliers,
    suppliersLoading,
    suppliersError,
    refreshSuppliers,
    addSupplier,
    updateSupplier,
    getSupplierById,
  } = useCatalogContext();

  return {
    suppliers,
    isLoading: suppliersLoading,
    error: suppliersError,
    refresh: refreshSuppliers,
    addSupplier,
    updateSupplier,
    getSupplierById,
  };
}
