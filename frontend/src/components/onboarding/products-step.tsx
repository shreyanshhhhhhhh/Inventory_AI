"use client";

import { Plus, Sparkles } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import {
  emptyProductForm,
  ProductFormFields,
  type ProductFormValues,
} from "@/components/catalog/product-form-fields";
import {
  formValuesToProduct,
  validateProductForm,
} from "@/components/catalog/product-schema";
import { FormDialog } from "@/components/common/form-dialog";
import { CatalogCsvImport } from "@/components/onboarding/catalog-csv-import";
import { StepFooter, type StepNavigation } from "@/components/onboarding/step-footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, showApiErrorToast } from "@/lib/api";
import type { ApiOnboardingStatus } from "@/lib/api-types";
import { useCategories, useProducts, useSuppliers } from "@/lib/catalog-hooks";

interface ProductsStepProps extends StepNavigation {
  status: ApiOnboardingStatus | null;
  onChanged: () => Promise<void>;
  onCatalogImported: () => Promise<void>;
}

type ProductFormErrors = Partial<Record<keyof ProductFormValues, string>>;

export function ProductsStep({
  status,
  onNext,
  onBack,
  onChanged,
  onCatalogImported,
}: ProductsStepProps) {
  const { products, total, isLoading, error, addProduct } = useProducts();
  const { categories, isLoading: categoriesLoading, addCategory } = useCategories();
  const { suppliers } = useSuppliers();
  const activeSuppliers = suppliers.filter((supplier) => supplier.isActive);
  const productCount = status?.product_count ?? total;

  const [formOpen, setFormOpen] = useState(false);
  const [formValues, setFormValues] = useState<ProductFormValues>(emptyProductForm);
  const [formErrors, setFormErrors] = useState<ProductFormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [addingCategory, setAddingCategory] = useState(false);
  const [loadingDemo, setLoadingDemo] = useState(false);

  const openCreate = () => {
    setFormValues(emptyProductForm);
    setFormErrors({});
    setNewCategoryName("");
    setFormOpen(true);
  };

  const handleAddCategory = async () => {
    const trimmed = newCategoryName.trim();
    if (!trimmed) return;
    setAddingCategory(true);
    try {
      const created = await addCategory(trimmed);
      setFormValues((current) => ({ ...current, categoryId: created.id }));
      setNewCategoryName("");
      toast.success("Category created");
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setAddingCategory(false);
    }
  };

  const handleSubmit = async () => {
    const errors = validateProductForm(
      formValues,
      products.map((product) => product.sku),
    );
    setFormErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setSubmitting(true);
    try {
      await addProduct(formValuesToProduct(formValues));
      await onChanged();
      toast.success("Product added");
      setFormOpen(false);
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleLoadDemoData = async () => {
    setLoadingDemo(true);
    try {
      const result = await api.onboarding.loadDemoData();
      await onCatalogImported();
      toast.success(result.message);
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setLoadingDemo(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="space-y-2 rounded-md border p-4">
          <p className="text-sm font-medium">Load demo data</p>
          <p className="text-xs text-muted-foreground">
            About 20 sample products with suppliers, stock, and an open purchase order. Only
            works while the catalog is empty.
          </p>
          <Button
            type="button"
            variant="secondary"
            onClick={() => void handleLoadDemoData()}
            disabled={loadingDemo || productCount > 0}
          >
            <Sparkles />
            {loadingDemo ? "Loading demo…" : "Load demo data"}
          </Button>
        </div>
        <div className="space-y-2 rounded-md border p-4">
          <p className="text-sm font-medium">Import a CSV</p>
          <p className="text-xs text-muted-foreground">
            Upload your catalog. Suppliers and opening quantities are created from the file.
          </p>
          <CatalogCsvImport onImported={onCatalogImported} />
        </div>
        <div className="space-y-2 rounded-md border p-4">
          <p className="text-sm font-medium">Add by hand</p>
          <p className="text-xs text-muted-foreground">
            {activeSuppliers.length === 0
              ? "Each product needs a preferred supplier. Add one in the previous step first."
              : "Enter products one at a time."}
          </p>
          <Button
            type="button"
            onClick={openCreate}
            disabled={activeSuppliers.length === 0}
          >
            <Plus />
            Add product
          </Button>
        </div>
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : products.length === 0 ? (
        <p className="rounded-md border border-dashed p-4 text-center text-sm text-muted-foreground">
          No products yet.
        </p>
      ) : (
        <div className="space-y-2">
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>SKU</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Preferred supplier</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {products.map((product) => (
                  <TableRow key={product.id}>
                    <TableCell className="font-mono text-xs">{product.sku}</TableCell>
                    <TableCell className="font-medium">{product.name}</TableCell>
                    <TableCell>{product.categoryName ?? "—"}</TableCell>
                    <TableCell>{product.preferredSupplierName ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {productCount > products.length ? (
            <p className="text-xs text-muted-foreground">
              Showing {products.length} of {productCount} products. The full list is in Catalog
              after setup.
            </p>
          ) : null}
        </div>
      )}

      <StepFooter
        onBack={onBack}
        onNext={onNext}
        nextLabel="Review"
        hint={productCount === 0 ? "At least one product is needed to finish." : undefined}
      />

      <FormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        title="Add product"
        description="Products are saved to your business catalog."
        submitLabel="Add product"
        isSubmitting={submitting}
        onSubmit={() => void handleSubmit()}
      >
        {categoriesLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="onboarding-new-category">
                {categories.length === 0 ? "Create a category first" : "New category (optional)"}
              </Label>
              <div className="flex gap-2">
                <Input
                  id="onboarding-new-category"
                  value={newCategoryName}
                  placeholder="e.g. Beverages"
                  onChange={(event) => setNewCategoryName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      void handleAddCategory();
                    }
                  }}
                />
                <Button
                  type="button"
                  variant="outline"
                  disabled={addingCategory || !newCategoryName.trim()}
                  onClick={() => void handleAddCategory()}
                >
                  Add
                </Button>
              </div>
            </div>
            <ProductFormFields
              values={formValues}
              categories={categories}
              suppliers={activeSuppliers}
              onChange={setFormValues}
              errors={formErrors}
            />
          </div>
        )}
      </FormDialog>
    </div>
  );
}
