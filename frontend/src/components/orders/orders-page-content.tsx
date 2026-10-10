"use client";

import { Plus, Truck } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { DataTable, type DataTableColumn } from "@/components/common/data-table";
import { EmptyState } from "@/components/common/empty-state";
import { FormDialog } from "@/components/common/form-dialog";
import { PageHeader } from "@/components/common/page-header";
import { StatusBadge } from "@/components/common/status-badge";
import { LoadErrorState } from "@/components/inventory/load-error-state";
import { PoDetailSheet } from "@/components/orders/po-detail-sheet";
import { SuppliersTabContent } from "@/components/orders/suppliers-tab-content";
import { Button } from "@/components/ui/button";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { showApiErrorToast } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useProducts, useSuppliers } from "@/lib/catalog-hooks";
import { useInventory } from "@/lib/inventory-hooks";
import { formatCurrency, formatDate } from "@/lib/format";
import {
  usePurchaseOrders,
  type TransitionAction,
} from "@/lib/purchase-orders-hooks";
import type { PurchaseOrder } from "@/types";

interface PoLineDraft {
  productId: string;
  quantity: string;
  unitCost: string;
}

export function OrdersPageContent() {
  const {
    purchaseOrders,
    isLoading,
    error,
    refreshPurchaseOrders,
    statusFilter,
    supplierFilter,
    setStatusFilter,
    setSupplierFilter,
    addPurchaseOrder,
    transitionPurchaseOrder,
    getPurchaseOrderTotal,
    getProductById,
  } = usePurchaseOrders();
  const { isOwner } = useAuth();
  const { suppliers } = useSuppliers();
  const activeSuppliers = suppliers.filter((supplier) => supplier.isActive);
  const { products } = useProducts();
  const { refreshStock, refreshMovements } = useInventory();

  const [selectedPo, setSelectedPo] = useState<PurchaseOrder | null>(null);
  const [poSheetOpen, setPoSheetOpen] = useState(false);
  const [newPoOpen, setNewPoOpen] = useState(false);
  const [poSupplierId, setPoSupplierId] = useState("");
  const [poExpectedDate, setPoExpectedDate] = useState("");
  const [poLines, setPoLines] = useState<PoLineDraft[]>([
    { productId: "", quantity: "", unitCost: "" },
  ]);
  const [submittingPo, setSubmittingPo] = useState(false);
  const [transitioning, setTransitioning] = useState(false);

  const poColumns: DataTableColumn<PurchaseOrder>[] = [
    { id: "poNumber", header: "PO number", cell: (row) => row.poNumber },
    {
      id: "supplier",
      header: "Supplier",
      cell: (row) =>
        suppliers.find((supplier) => supplier.id === row.supplierId)?.name ??
        "—",
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => <StatusBadge variant={row.status} />,
    },
    {
      id: "total",
      header: "Total",
      cell: (row) => formatCurrency(getPurchaseOrderTotal(row)),
    },
    {
      id: "expectedDate",
      header: "Expected date",
      cell: (row) => (row.expectedDate ? formatDate(row.expectedDate) : "—"),
    },
  ];

  const poRunningTotal = useMemo(() => {
    return poLines.reduce((sum, line) => {
      const qty = Number(line.quantity) || 0;
      const cost = Number(line.unitCost) || 0;
      return sum + qty * cost;
    }, 0);
  }, [poLines]);

  const openPoDetail = (order: PurchaseOrder) => {
    setSelectedPo(order);
    setPoSheetOpen(true);
  };

  const submitPurchaseOrder = async () => {
    const validLines = poLines.filter(
      (line) => line.productId && Number(line.quantity) > 0,
    );
    if (!poSupplierId || !poExpectedDate || validLines.length === 0) {
      toast.error("Supplier, expected date, and at least one line are required.");
      return;
    }

    setSubmittingPo(true);
    try {
      await addPurchaseOrder({
        supplierId: poSupplierId,
        expectedDate: poExpectedDate,
        lineItems: validLines.map((line) => ({
          productId: line.productId,
          quantity: Number(line.quantity),
          unitCost: Number(line.unitCost) || 0,
        })),
      });
      toast.success("Purchase order created");
      setNewPoOpen(false);
      setPoSupplierId("");
      setPoExpectedDate("");
      setPoLines([{ productId: "", quantity: "", unitCost: "" }]);
    } catch (error) {
      showApiErrorToast(error);
    } finally {
      setSubmittingPo(false);
    }
  };

  const handleTransition = async (action: TransitionAction) => {
    if (!selectedPo) return;
    if (action === "approve" && !isOwner) {
      toast.error("Only an owner can approve purchase orders.");
      return;
    }
    setTransitioning(true);
    try {
      const updated = await transitionPurchaseOrder(selectedPo.id, action);
      setSelectedPo(updated);
      const labels: Record<TransitionAction, string> = {
        approve: "Purchase order approved",
        send: "Purchase order marked sent",
        receive: "Purchase order received",
        cancel: "Purchase order cancelled",
      };
      toast.success(labels[action]);
      if (action === "receive") {
        await Promise.all([refreshStock(), refreshMovements()]);
      }
    } catch (error) {
      showApiErrorToast(error);
    } finally {
      setTransitioning(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Orders & Suppliers"
        description="Create purchase orders and manage supplier contacts."
      />

      <Tabs defaultValue="purchase-orders">
        <TabsList>
          <TabsTrigger value="purchase-orders">Purchase orders</TabsTrigger>
          <TabsTrigger value="suppliers">Suppliers</TabsTrigger>
        </TabsList>

        <TabsContent value="purchase-orders" className="mt-4 space-y-4">
          <div className="flex justify-end">
            <Button onClick={() => setNewPoOpen(true)}>
              <Plus />
              New PO
            </Button>
          </div>
          {isLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : error ? (
            <LoadErrorState
              title="Could not load purchase orders"
              message={error}
              onRetry={refreshPurchaseOrders}
            />
          ) : (
            <DataTable
              data={purchaseOrders}
              columns={poColumns}
              getRowId={(row) => row.id}
              onRowClick={openPoDetail}
              hideSearch
              toolbar={
                <>
                  <Select
                    value={statusFilter}
                    onValueChange={(value) => setStatusFilter(value ?? "all")}
                  >
                    <SelectTrigger className="w-40">
                      <SelectValue placeholder="Status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All statuses</SelectItem>
                      <SelectItem value="draft">Draft</SelectItem>
                      <SelectItem value="approved">Approved</SelectItem>
                      <SelectItem value="sent">Sent</SelectItem>
                      <SelectItem value="received">Received</SelectItem>
                      <SelectItem value="cancelled">Cancelled</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select
                    value={supplierFilter}
                    onValueChange={(value) => setSupplierFilter(value ?? "all")}
                  >
                    <SelectTrigger className="w-44">
                      <SelectValue placeholder="Supplier" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All suppliers</SelectItem>
                      {suppliers.map((supplier) => (
                        <SelectItem key={supplier.id} value={supplier.id}>
                          {supplier.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </>
              }
              emptyState={
                <EmptyState
                  icon={Truck}
                  title="No purchase orders"
                  message="Create a draft purchase order to restock low items."
                  action={
                    <Button onClick={() => setNewPoOpen(true)}>
                      <Plus />
                      New PO
                    </Button>
                  }
                />
              }
            />
          )}
        </TabsContent>

        <TabsContent value="suppliers" className="mt-4">
          <SuppliersTabContent />
        </TabsContent>
      </Tabs>

      <PoDetailSheet
        order={selectedPo}
        open={poSheetOpen}
        onOpenChange={setPoSheetOpen}
        supplierName={
          suppliers.find((supplier) => supplier.id === selectedPo?.supplierId)
            ?.name ?? "—"
        }
        getProductName={(productId) =>
          getProductById(productId)?.name ?? "Unknown"
        }
        total={selectedPo ? getPurchaseOrderTotal(selectedPo) : 0}
        onTransition={(action) => void handleTransition(action)}
        isSubmitting={transitioning}
        canApprove={isOwner}
      />

      <FormDialog
        open={newPoOpen}
        onOpenChange={setNewPoOpen}
        title="New purchase order"
        description="Line costs default from the catalog when you pick a product."
        submitLabel={submittingPo ? "Creating…" : "Create PO"}
        onSubmit={() => void submitPurchaseOrder()}
      >
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Supplier</Label>
            <Select
              value={poSupplierId}
              onValueChange={(value) => setPoSupplierId(value ?? "")}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select supplier" />
              </SelectTrigger>
              <SelectContent>
                {activeSuppliers.map((supplier) => (
                  <SelectItem key={supplier.id} value={supplier.id}>
                    {supplier.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="expected-date">Expected date</Label>
            <Input
              id="expected-date"
              type="date"
              value={poExpectedDate}
              onChange={(event) => setPoExpectedDate(event.target.value)}
            />
          </div>
          <div className="space-y-3">
            <Label>Line items</Label>
            {poLines.map((line, index) => (
              <div key={index} className="grid gap-2 rounded-lg border p-3">
                <Select
                  value={line.productId}
                  onValueChange={(value) => {
                    const product = products.find((item) => item.id === value);
                    const next = [...poLines];
                    next[index] = {
                      ...line,
                      productId: value ?? "",
                      unitCost: product ? product.cost.toFixed(2) : line.unitCost,
                    };
                    setPoLines(next);
                  }}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Product" />
                  </SelectTrigger>
                  <SelectContent>
                    {products.map((product) => (
                      <SelectItem key={product.id} value={product.id}>
                        {product.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <div className="grid grid-cols-2 gap-2">
                  <Input
                    placeholder="Qty"
                    inputMode="numeric"
                    value={line.quantity}
                    onChange={(event) => {
                      const next = [...poLines];
                      next[index] = { ...line, quantity: event.target.value };
                      setPoLines(next);
                    }}
                  />
                  <Input
                    placeholder="Unit cost"
                    inputMode="decimal"
                    value={line.unitCost}
                    onChange={(event) => {
                      const next = [...poLines];
                      next[index] = { ...line, unitCost: event.target.value };
                      setPoLines(next);
                    }}
                  />
                </div>
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              onClick={() =>
                setPoLines([
                  ...poLines,
                  { productId: "", quantity: "", unitCost: "" },
                ])
              }
            >
              Add line
            </Button>
          </div>
          <p className="text-sm font-medium">
            Running total: {formatCurrency(poRunningTotal)}
          </p>
        </div>
      </FormDialog>
    </>
  );
}
