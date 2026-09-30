import { z } from "zod";

import type { ProductFormValues } from "@/components/catalog/product-form-fields";

export const productSchema = z.object({
  sku: z.string().trim().min(1, "SKU is required"),
  name: z.string().trim().min(1, "Name is required"),
  categoryId: z.string().min(1, "Category is required"),
  unit: z.enum(["each", "case", "lb", "oz", "pack"]),
  cost: z
    .string()
    .trim()
    .refine((value) => !Number.isNaN(Number(value)) && Number(value) >= 0, {
      message: "Cost must be 0 or greater",
    }),
  price: z
    .string()
    .trim()
    .refine((value) => !Number.isNaN(Number(value)) && Number(value) >= 0, {
      message: "Price must be 0 or greater",
    }),
  reorderPoint: z
    .string()
    .trim()
    .refine(
      (value) => Number.isInteger(Number(value)) && Number(value) >= 0,
      { message: "Reorder point must be a whole number 0 or greater" },
    ),
  safetyStock: z.string().trim(),
  preferredSupplierId: z.string().min(1, "Preferred supplier is required"),
});

export function validateProductForm(
  values: ProductFormValues,
  existingSkus: string[],
  editingSku?: string,
): Partial<Record<keyof ProductFormValues, string>> {
  const parsed = productSchema.safeParse(values);
  const errors: Partial<Record<keyof ProductFormValues, string>> = {};

  if (!parsed.success) {
    for (const issue of parsed.error.issues) {
      const field = issue.path[0];
      if (typeof field === "string" && !errors[field as keyof ProductFormValues]) {
        errors[field as keyof ProductFormValues] = issue.message;
      }
    }
  }

  const sku = values.sku.trim().toUpperCase();
  const duplicate = existingSkus.some(
    (existing) =>
      existing.toUpperCase() === sku &&
      existing.toUpperCase() !== editingSku?.toUpperCase(),
  );
  if (duplicate) {
    errors.sku = "SKU must be unique";
  }

  return errors;
}

export function formValuesToProduct(
  values: ProductFormValues,
): Omit<
  import("@/types").Product,
  "id" | "categoryName" | "preferredSupplierName"
> {
  return {
    sku: values.sku.trim(),
    name: values.name.trim(),
    categoryId: values.categoryId,
    unit: values.unit,
    cost: Number(values.cost),
    price: Number(values.price),
    reorderPoint: Number(values.reorderPoint),
    safetyStock: Number(values.safetyStock) || 0,
    preferredSupplierId: values.preferredSupplierId,
    isActive: true,
  };
}
