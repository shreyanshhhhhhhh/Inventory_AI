"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Category, Product, ProductUnit, Supplier } from "@/types";

export interface ProductFormValues {
  sku: string;
  name: string;
  categoryId: string;
  unit: ProductUnit;
  cost: string;
  price: string;
  reorderPoint: string;
  safetyStock: string;
  preferredSupplierId: string;
}

export const emptyProductForm: ProductFormValues = {
  sku: "",
  name: "",
  categoryId: "",
  unit: "each",
  cost: "",
  price: "",
  reorderPoint: "",
  safetyStock: "",
  preferredSupplierId: "",
};

export function productToFormValues(product: Product): ProductFormValues {
  return {
    sku: product.sku,
    name: product.name,
    categoryId: product.categoryId ?? "",
    unit: product.unit,
    cost: product.cost.toFixed(2),
    price: product.price.toFixed(2),
    reorderPoint: String(product.reorderPoint),
    safetyStock: String(product.safetyStock),
    preferredSupplierId: product.preferredSupplierId ?? "",
  };
}

interface ProductFormFieldsProps {
  values: ProductFormValues;
  categories: Category[];
  suppliers: Supplier[];
  onChange: (values: ProductFormValues) => void;
  errors: Partial<Record<keyof ProductFormValues, string>>;
}

export function ProductFormFields({
  values,
  categories,
  suppliers,
  onChange,
  errors,
}: ProductFormFieldsProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="space-y-2">
        <Label htmlFor="sku">SKU</Label>
        <Input
          id="sku"
          value={values.sku}
          onChange={(event) =>
            onChange({ ...values, sku: event.target.value })
          }
          aria-invalid={Boolean(errors.sku)}
        />
        {errors.sku ? (
          <p className="text-xs text-destructive">{errors.sku}</p>
        ) : null}
      </div>
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <Input
          id="name"
          value={values.name}
          onChange={(event) =>
            onChange({ ...values, name: event.target.value })
          }
          aria-invalid={Boolean(errors.name)}
        />
        {errors.name ? (
          <p className="text-xs text-destructive">{errors.name}</p>
        ) : null}
      </div>
      <div className="space-y-2">
        <Label>Category</Label>
        <Select
          value={values.categoryId}
          onValueChange={(value) =>
            onChange({ ...values, categoryId: value ?? "" })
          }
        >
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Select category" />
          </SelectTrigger>
          <SelectContent>
            {categories.map((category) => (
              <SelectItem key={category.id} value={category.id}>
                {category.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {errors.categoryId ? (
          <p className="text-xs text-destructive">{errors.categoryId}</p>
        ) : null}
      </div>
      <div className="space-y-2">
        <Label>Unit</Label>
        <Select
          value={values.unit}
          onValueChange={(value) =>
            onChange({ ...values, unit: value as ProductUnit })
          }
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="each">Each</SelectItem>
            <SelectItem value="case">Case</SelectItem>
            <SelectItem value="lb">Lb</SelectItem>
            <SelectItem value="oz">Oz</SelectItem>
            <SelectItem value="pack">Pack</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="cost">Cost</Label>
        <Input
          id="cost"
          inputMode="decimal"
          value={values.cost}
          onChange={(event) =>
            onChange({ ...values, cost: event.target.value })
          }
          aria-invalid={Boolean(errors.cost)}
        />
        {errors.cost ? (
          <p className="text-xs text-destructive">{errors.cost}</p>
        ) : null}
      </div>
      <div className="space-y-2">
        <Label htmlFor="price">Price</Label>
        <Input
          id="price"
          inputMode="decimal"
          value={values.price}
          onChange={(event) =>
            onChange({ ...values, price: event.target.value })
          }
          aria-invalid={Boolean(errors.price)}
        />
        {errors.price ? (
          <p className="text-xs text-destructive">{errors.price}</p>
        ) : null}
      </div>
      <div className="space-y-2">
        <Label htmlFor="reorderPoint">Reorder point</Label>
        <Input
          id="reorderPoint"
          inputMode="numeric"
          value={values.reorderPoint}
          onChange={(event) =>
            onChange({ ...values, reorderPoint: event.target.value })
          }
          aria-invalid={Boolean(errors.reorderPoint)}
        />
        {errors.reorderPoint ? (
          <p className="text-xs text-destructive">{errors.reorderPoint}</p>
        ) : null}
      </div>
      <div className="space-y-2">
        <Label htmlFor="safetyStock">Safety stock</Label>
        <Input
          id="safetyStock"
          inputMode="numeric"
          value={values.safetyStock}
          onChange={(event) =>
            onChange({ ...values, safetyStock: event.target.value })
          }
        />
      </div>
      <div className="space-y-2 sm:col-span-2">
        <Label>Preferred supplier</Label>
        <Select
          value={values.preferredSupplierId}
          onValueChange={(value) =>
            onChange({ ...values, preferredSupplierId: value ?? "" })
          }
        >
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Select supplier" />
          </SelectTrigger>
          <SelectContent>
            {suppliers.map((supplier) => (
              <SelectItem key={supplier.id} value={supplier.id}>
                {supplier.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
