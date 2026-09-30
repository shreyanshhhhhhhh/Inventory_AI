import type {
  ApiCategory,
  ApiLocation,
  ApiMovement,
  ApiPurchaseOrder,
  ApiProduct,
  ApiProductWrite,
  ApiStockLevel,
  ApiSupplier,
  ApiSupplierWrite,
} from "@/lib/api-types";
import type {
  Category,
  Location,
  MovementType,
  Product,
  ProductUnit,
  StockLevel,
  PurchaseOrder,
  StockMovement,
  Supplier,
} from "@/types";

function parseMoney(value: string | null | undefined): number {
  if (value === null || value === undefined || value === "") return 0;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function parseQuantity(value: string | null | undefined): number {
  if (value === null || value === undefined || value === "") return 0;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function toMoneyString(value: number): string {
  return value.toFixed(2);
}

function toQuantityString(value: number): string {
  return String(value);
}

export function mapCategory(api: ApiCategory): Category {
  return { id: api.id, name: api.name };
}

export function mapSupplier(api: ApiSupplier): Supplier {
  return {
    id: api.id,
    name: api.name,
    email: api.email ?? "",
    phone: api.phone ?? "",
    leadTimeDays: api.lead_time_days,
    isActive: api.is_active,
  };
}

export function mapProduct(api: ApiProduct): Product {
  return {
    id: api.id,
    sku: api.sku,
    name: api.name,
    categoryId: api.category_id,
    categoryName: api.category_name,
    unit: api.unit as ProductUnit,
    cost: parseMoney(api.cost),
    price: parseMoney(api.price),
    reorderPoint: parseQuantity(api.reorder_point),
    safetyStock: parseQuantity(api.safety_stock),
    preferredSupplierId: api.preferred_supplier_id,
    preferredSupplierName: api.preferred_supplier_name,
    isActive: api.is_active,
  };
}

export function mapProductWrite(
  product: Omit<Product, "id" | "categoryName" | "preferredSupplierName">,
): ApiProductWrite {
  return {
    sku: product.sku,
    name: product.name,
    category_id: product.categoryId,
    unit: product.unit,
    cost: toMoneyString(product.cost),
    price: toMoneyString(product.price),
    reorder_point: toQuantityString(product.reorderPoint),
    safety_stock: toQuantityString(product.safetyStock),
    preferred_supplier_id: product.preferredSupplierId,
  };
}

export function mapSupplierWrite(
  supplier: Omit<Supplier, "id" | "isActive">,
): ApiSupplierWrite {
  return {
    name: supplier.name,
    email: supplier.email || null,
    phone: supplier.phone || null,
    lead_time_days: supplier.leadTimeDays,
  };
}

export function mapLocation(api: ApiLocation): Location {
  return {
    id: api.id,
    name: api.name,
    isDefault: api.is_default,
  };
}

export function mapStockLevel(api: ApiStockLevel): StockLevel & {
  sku: string;
  productName: string;
  locationName: string;
  reorderPoint: number;
  status: ApiStockLevel["status"];
} {
  return {
    productId: api.product_id,
    locationId: api.location_id,
    onHand: parseQuantity(api.on_hand),
    sku: api.sku,
    productName: api.product_name,
    locationName: api.location_name,
    reorderPoint: parseQuantity(api.reorder_point),
    status: api.status,
  };
}

function mapMovementType(type: ApiMovement["movement_type"]): MovementType {
  if (type === "purchase_receipt") return "receipt";
  return type;
}

export function mapPurchaseOrder(api: ApiPurchaseOrder): PurchaseOrder & {
  supplierName: string;
  total: number;
  locationId: string;
} {
  return {
    id: api.id,
    poNumber: api.po_number,
    supplierId: api.supplier_id,
    supplierName: api.supplier_name,
    locationId: api.location_id,
    status: api.status,
    expectedDate: api.expected_date ?? "",
    lineItems: api.line_items.map((line) => ({
      id: line.id,
      productId: line.product_id,
      quantity: parseQuantity(line.quantity),
      unitCost: parseMoney(line.unit_cost),
    })),
    total: parseMoney(api.total),
  };
}

export function mapMovement(api: ApiMovement): StockMovement & {
  productName: string;
  locationName: string;
  userName: string;
} {
  return {
    id: api.id,
    date: api.occurred_at,
    productId: api.product_id,
    locationId: api.location_id,
    type: mapMovementType(api.movement_type),
    quantity: parseQuantity(api.quantity),
    userId: api.user_id,
    note: api.reason ?? api.note ?? "",
    productName: api.product_name,
    locationName: api.location_name,
    userName: api.user_name,
  };
}
