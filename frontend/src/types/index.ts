export type ProductUnit = "each" | "case" | "lb" | "oz" | "pack";

export type MovementType = "receipt" | "sale" | "adjustment" | "transfer";

export type PurchaseOrderStatus =
  | "draft"
  | "approved"
  | "sent"
  | "received"
  | "cancelled";

export type StockStatus = "in-stock" | "low" | "out";

export type UserRole = "owner" | "staff";

export interface Category {
  id: string;
  name: string;
}

export interface Product {
  id: string;
  sku: string;
  name: string;
  categoryId: string | null;
  categoryName: string | null;
  unit: ProductUnit;
  cost: number;
  price: number;
  reorderPoint: number;
  safetyStock: number;
  preferredSupplierId: string | null;
  preferredSupplierName: string | null;
  isActive: boolean;
}

export interface Supplier {
  id: string;
  name: string;
  email: string;
  phone: string;
  leadTimeDays: number;
  isActive: boolean;
}

export interface Location {
  id: string;
  name: string;
  isDefault: boolean;
}

export interface StockLevel {
  productId: string;
  locationId: string;
  onHand: number;
}

export interface StockMovement {
  id: string;
  date: string;
  productId: string;
  locationId: string;
  type: MovementType;
  quantity: number;
  userId: string;
  note: string;
}

export interface PurchaseOrderLine {
  id: string;
  productId: string;
  quantity: number;
  unitCost: number;
}

export interface PurchaseOrder {
  id: string;
  poNumber: string;
  supplierId: string;
  status: PurchaseOrderStatus;
  expectedDate: string;
  lineItems: PurchaseOrderLine[];
}

export interface BusinessProfile {
  name: string;
  currency: string;
}

export interface TeamUser {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  active: boolean;
}

export interface DashboardStats {
  totalStockValue: number;
  itemsBelowReorder: number;
  openPurchaseOrders: number;
  pendingApprovals: number;
}
