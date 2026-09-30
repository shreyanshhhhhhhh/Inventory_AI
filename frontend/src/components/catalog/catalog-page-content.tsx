"use client";

import {
  ChevronLeft,
  ChevronRight,
  MoreHorizontal,
  Package,
  Plus,
  Sparkles,
  Upload,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import {
  emptyProductForm,
  ProductFormFields,
  productToFormValues,
  type ProductFormValues,
} from "@/components/catalog/product-form-fields";
import {
  formValuesToProduct,
  validateProductForm,
} from "@/components/catalog/product-schema";
import { CsvImportDialog } from "@/components/common/csv-import-dialog";
import { DataTable, type DataTableColumn } from "@/components/common/data-table";
import { EmptyState } from "@/components/common/empty-state";
import { FormDialog } from "@/components/common/form-dialog";
import { PageHeader } from "@/components/common/page-header";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError, showApiErrorToast } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useCategories, useProducts, useSuppliers } from "@/lib/catalog-hooks";
import { useInventory } from "@/lib/inventory-hooks";
import { usePurchaseOrders } from "@/lib/purchase-orders-hooks";
import { formatCurrency } from "@/lib/format";
import type { Product } from "@/types";

export function CatalogPageContent() {
  const { user } = useAuth();
  const {
    products,
    total,
    page,
    pageSize,
    isLoading,
    error,
    search,
    categoryFilter,
    setSearch,
    setCategoryFilter,
    setPage,
    refresh,
    addProduct,
    updateProduct,
    deleteProduct,
  } = useProducts();
  const { categories, isLoading: categoriesLoading, addCategory } =
    useCategories();
  const { suppliers, refresh: refreshSuppliers } = useSuppliers();
  const { refreshStock, refreshMovements } = useInventory();
  const { refreshPurchaseOrders } = usePurchaseOrders();

  const [formOpen, setFormOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [categoryDialogOpen, setCategoryDialogOpen] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Product | null>(null);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [formValues, setFormValues] =
    useState<ProductFormValues>(emptyProductForm);
  const [formErrors, setFormErrors] = useState<
    Partial<Record<keyof ProductFormValues, string>>
  >({});
  const [submitting, setSubmitting] = useState(false);
  const [loadingDemo, setLoadingDemo] = useState(false);
  const [searchInput, setSearchInput] = useState(search);
  const isOwner = user?.role === "owner";

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput, setSearch, setPage]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const openCreate = () => {
    setEditingProduct(null);
    setFormValues(emptyProductForm);
    setFormErrors({});
    setFormOpen(true);
  };

  const openEdit = (product: Product) => {
    setEditingProduct(product);
    setFormValues(productToFormValues(product));
    setFormErrors({});
    setFormOpen(true);
  };

  const handleSubmit = async () => {
    const errors = validateProductForm(
      formValues,
      products.map((product) => product.sku),
      editingProduct?.sku,
    );
    setFormErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setSubmitting(true);
    try {
      const payload = formValuesToProduct(formValues);
      if (editingProduct) {
        await updateProduct(editingProduct.id, payload);
        toast.success("Product updated");
      } else {
        await addProduct(payload);
        toast.success("Product added");
      }
      setFormOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save product.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteProduct(deleteTarget.id);
      toast.success("Product deleted");
      setDeleteTarget(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not delete product.");
    }
  };

  const refreshAfterImport = async () => {
    await Promise.all([
      refresh(),
      refreshSuppliers(),
      refreshStock(),
      refreshMovements(),
    ]);
  };

  const handleLoadDemoData = async () => {
    setLoadingDemo(true);
    try {
      const result = await api.onboarding.loadDemoData();
      await Promise.all([
        refresh(),
        refreshSuppliers(),
        refreshStock(),
        refreshMovements(),
        refreshPurchaseOrders(),
      ]);
      toast.success(result.message);
    } catch (err) {
      if (err instanceof ApiError) {
        toast.error(err.message);
        return;
      }
      showApiErrorToast(err);
    } finally {
      setLoadingDemo(false);
    }
  };

  const handleAddCategory = async () => {
    if (!newCategoryName.trim()) {
      toast.error("Category name is required.");
      return;
    }
    try {
      await addCategory(newCategoryName.trim());
      toast.success("Category created");
      setCategoryDialogOpen(false);
      setNewCategoryName("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create category.");
    }
  };

  const columns: DataTableColumn<Product>[] = [
    { id: "sku", header: "SKU", cell: (row) => row.sku },
    { id: "name", header: "Name", cell: (row) => row.name },
    {
      id: "category",
      header: "Category",
      cell: (row) => row.categoryName ?? "—",
    },
    { id: "unit", header: "Unit", cell: (row) => row.unit },
    {
      id: "cost",
      header: "Cost",
      cell: (row) => formatCurrency(row.cost),
    },
    {
      id: "price",
      header: "Price",
      cell: (row) => formatCurrency(row.price),
    },
    {
      id: "reorderPoint",
      header: "Reorder point",
      cell: (row) => row.reorderPoint,
    },
    {
      id: "supplier",
      header: "Preferred supplier",
      cell: (row) => row.preferredSupplierName ?? "—",
    },
    {
      id: "actions",
      header: "",
      className: "w-12 text-right",
      cell: (row) => (
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button variant="ghost" size="icon-sm" aria-label="Row actions" />
            }
          >
            <MoreHorizontal />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => openEdit(row)}>
              Edit
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setDeleteTarget(row)}>
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Catalog"
        description="Manage products, pricing, and reorder settings."
        action={
          <>
            <Button variant="outline" onClick={() => setCategoryDialogOpen(true)}>
              Add category
            </Button>
            <Button variant="outline" onClick={() => setImportOpen(true)}>
              <Upload />
              Import CSV
            </Button>
            <Button onClick={openCreate}>
              <Plus />
              Add product
            </Button>
          </>
        }
      />

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-8 w-full max-w-sm" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : (
        <>
          <div className="relative w-full max-w-sm">
            <Input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Search by name or SKU…"
              className="pl-3"
            />
          </div>

          <DataTable
            data={products}
            columns={columns}
            getRowId={(row) => row.id}
            pageSize={pageSize}
            hideSearch
            toolbar={
              <>
                <Select
                  value={categoryFilter}
                  onValueChange={(value) => {
                    setCategoryFilter(value ?? "all");
                    setPage(1);
                  }}
                >
                  <SelectTrigger className="w-44">
                    <SelectValue placeholder="Category" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All categories</SelectItem>
                    {categories.map((category) => (
                      <SelectItem key={category.id} value={category.id}>
                        {category.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </>
            }
            emptyState={
              <EmptyState
                icon={Package}
                title="No products yet"
                message="Add your first product, import a CSV, or load demo data to explore the app."
                action={
                  <div className="flex flex-wrap justify-center gap-2">
                    {isOwner ? (
                      <Button
                        variant="secondary"
                        onClick={() => void handleLoadDemoData()}
                        disabled={loadingDemo}
                      >
                        <Sparkles />
                        {loadingDemo ? "Loading demo…" : "Load demo data"}
                      </Button>
                    ) : null}
                    <Button variant="outline" onClick={() => setImportOpen(true)}>
                      <Upload />
                      Import CSV
                    </Button>
                    <Button onClick={openCreate}>
                      <Plus />
                      Add product
                    </Button>
                  </div>
                }
              />
            }
          />

          {total > pageSize ? (
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <p>
                Showing {(page - 1) * pageSize + 1}–
                {Math.min(page * pageSize, total)} of {total}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="icon-sm"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                  aria-label="Previous page"
                >
                  <ChevronLeft />
                </Button>
                <span>
                  Page {page} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="icon-sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage(page + 1)}
                  aria-label="Next page"
                >
                  <ChevronRight />
                </Button>
              </div>
            </div>
          ) : null}
        </>
      )}

      <FormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        title={editingProduct ? "Edit product" : "Add product"}
        description="Products are saved to your business catalog."
        submitLabel={editingProduct ? "Save changes" : "Add product"}
        isSubmitting={submitting}
        onSubmit={() => void handleSubmit()}
      >
        {categoriesLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <ProductFormFields
            values={formValues}
            categories={categories}
            suppliers={suppliers}
            onChange={setFormValues}
            errors={formErrors}
          />
        )}
      </FormDialog>

      <CsvImportDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        title="Import CSV"
        description="Upload a catalog CSV. Rows with opening quantity post an adjustment movement."
        sampleCsvPath={api.products.sampleCsvHref}
        sampleFileName="catalog-sample.csv"
        onImport={(file, options) => api.products.importCsv(file, options)}
        onSuccess={refreshAfterImport}
      />

      <Dialog open={categoryDialogOpen} onOpenChange={setCategoryDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add category</DialogTitle>
            <DialogDescription>
              Categories are shared across your product catalog.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="category-name">Name</Label>
            <Input
              id="category-name"
              value={newCategoryName}
              onChange={(event) => setNewCategoryName(event.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCategoryDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void handleAddCategory()}>Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete product?</DialogTitle>
            <DialogDescription>
              {deleteTarget
                ? `Archive ${deleteTarget.name} (${deleteTarget.sku})? It will be hidden from the catalog.`
                : null}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={() => void handleDelete()}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
