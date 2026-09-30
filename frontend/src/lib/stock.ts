import type { StockStatus } from "@/types";

export function getStockStatus(onHand: number, reorderPoint: number): StockStatus {
  if (onHand <= 0) return "out";
  if (reorderPoint > 0 && onHand <= reorderPoint) return "low";
  return "in-stock";
}

export function mapApiStockStatus(status: "in_stock" | "low" | "out"): StockStatus {
  if (status === "in_stock") return "in-stock";
  return status;
}
