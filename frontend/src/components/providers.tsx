"use client";

import type { ReactNode } from "react";

import { AuthProvider } from "@/lib/auth-context";
import { Toaster } from "@/components/ui/sonner";
import { CatalogProvider } from "@/lib/catalog-hooks";
import { DashboardProvider } from "@/lib/dashboard-hooks";
import { InventoryProvider } from "@/lib/inventory-hooks";
import { ReportsProvider } from "@/lib/reports-hooks";
import { SettingsProvider } from "@/lib/settings-hooks";
import { MockStoreProvider } from "@/lib/mock-store";
import { PurchaseOrdersProvider } from "@/lib/purchase-orders-hooks";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <CatalogProvider>
        <InventoryProvider>
          <PurchaseOrdersProvider>
            <DashboardProvider>
              <ReportsProvider>
                <SettingsProvider>
                  <MockStoreProvider>
                    {children}
                    <Toaster richColors closeButton position="top-right" />
                  </MockStoreProvider>
                </SettingsProvider>
              </ReportsProvider>
            </DashboardProvider>
          </PurchaseOrdersProvider>
        </InventoryProvider>
      </CatalogProvider>
    </AuthProvider>
  );
}
