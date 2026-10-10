"use client";

import {
  ArrowDownUp,
  ArrowRightLeft,
  ShoppingCart,
  Upload,
  Warehouse,
} from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { CsvImportDialog } from "@/components/common/csv-import-dialog";
import { DataTable, type DataTableColumn } from "@/components/common/data-table";
import { EmptyState } from "@/components/common/empty-state";
import { FormDialog } from "@/components/common/form-dialog";
import { PageHeader } from "@/components/common/page-header";
import {
  StatusBadge,
  type StatusBadgeVariant,
} from "@/components/common/status-badge";
import { LoadErrorState } from "@/components/inventory/load-error-state";
import { RecordSaleDialog } from "@/components/inventory/record-sale-dialog";
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
import { api, showApiErrorToast } from "@/lib/api";
import { useInventory } from "@/lib/inventory-hooks";
import { formatDateTime } from "@/lib/format";
import { mapApiStockStatus } from "@/lib/stock";
import type { MovementType, StockMovement } from "@/types";

interface StockRow {
  id: string;
  productId: string;
  locationId: string;
  sku: string;
  productName: string;
  locationName: string;
  onHand: number;
  reorderPoint: number;
  status: ReturnType<typeof mapApiStockStatus>;
}

type ManualMovementType = Exclude<MovementType, "sale">;

const movementBadgeVariant: Record<MovementType, StatusBadgeVariant> = {
  receipt: "received",
  sale: "sent",
  adjustment: "draft",
  transfer: "approved",
};

export function InventoryPageContent() {
  const {
    products,
    locations,
    stockLevels,
    movements,
    stockLoading,
    movementsLoading,
    stockError,
    movementsError,
    stockSearch,
    locationFilter,
    lowStockOnly,
    movementTypeFilter,
    setStockSearch,
    setLocationFilter,
    setLowStockOnly,
    setMovementTypeFilter,
    recordMovement,
    refreshStock,
    refreshMovements,
  } = useInventory();

  const [importOpen, setImportOpen] = useState(false);
  const [saleOpen, setSaleOpen] = useState(false);
  const [saleDialogKey, setSaleDialogKey] = useState(0);
  const [movementOpen, setMovementOpen] = useState(false);
  const [movementProductId, setMovementProductId] = useState("");
  const [movementLocationId, setMovementLocationId] = useState("");
  const [movementDestinationId, setMovementDestinationId] = useState("");
  const [movementType, setMovementType] =
    useState<ManualMovementType>("receipt");
  const [movementQuantity, setMovementQuantity] = useState("");
  const [movementNote, setMovementNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const defaultLocationId =
    (locations.find((location) => location.isDefault) ?? locations[0])?.id ??
    "";
  const effectiveLocationId = movementLocationId || defaultLocationId;
  const effectiveDestinationId =
    movementDestinationId !== effectiveLocationId ? movementDestinationId : "";
  const destinationOptions = locations.filter(
    (location) => location.id !== effectiveLocationId,
  );
  const isTransfer = movementType === "transfer";

  const stockRows = useMemo<StockRow[]>(() => {
    return stockLevels.map((level) => ({
      id: `${level.productId}-${level.locationId}`,
      productId: level.productId,
      locationId: level.locationId,
      sku: level.sku,
      productName: level.productName,
      locationName: level.locationName,
      onHand: level.onHand,
      reorderPoint: level.reorderPoint,
      status: mapApiStockStatus(level.status),
    }));
  }, [stockLevels]);

  const stockColumns: DataTableColumn<StockRow>[] = [
    { id: "sku", header: "SKU", cell: (row) => row.sku },
    { id: "product", header: "Product", cell: (row) => row.productName },
    { id: "location", header: "Location", cell: (row) => row.locationName },
    { id: "onHand", header: "On hand", cell: (row) => row.onHand },
    {
      id: "reorderPoint",
      header: "Reorder point",
      cell: (row) => row.reorderPoint,
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => <StatusBadge variant={row.status} />,
    },
  ];

  const movementColumns: DataTableColumn<
    StockMovement & { productName: string; locationName: string; userName: string }
  >[] = [
    {
      id: "date",
      header: "Date",
      cell: (row) => formatDateTime(row.date),
    },
    {
      id: "product",
      header: "Product",
      cell: (row) => row.productName,
    },
    {
      id: "location",
      header: "Location",
      cell: (row) => row.locationName,
    },
    {
      id: "type",
      header: "Type",
      cell: (row) => (
        <StatusBadge variant={movementBadgeVariant[row.type]} label={row.type} />
      ),
    },
    {
      id: "quantity",
      header: "Quantity",
      cell: (row) => (
        <span
          className={
            row.quantity > 0 ? "text-emerald-600" : "text-red-600"
          }
        >
          {row.quantity > 0 ? `+${row.quantity}` : row.quantity}
        </span>
      ),
    },
    {
      id: "user",
      header: "User",
      cell: (row) => row.userName,
    },
    { id: "note", header: "Note", cell: (row) => row.note || "—" },
  ];

  const openMovement = (type: ManualMovementType) => {
    setMovementType(type);
    setMovementOpen(true);
  };

  const openSale = () => {
    setSaleDialogKey((key) => key + 1);
    setSaleOpen(true);
  };

  const submitMovement = async () => {
    const quantity = Number(movementQuantity);
    const requiresPositive = movementType !== "adjustment";
    if (
      !movementProductId ||
      !effectiveLocationId ||
      !Number.isFinite(quantity) ||
      (requiresPositive && quantity <= 0) ||
      (movementType === "adjustment" && quantity === 0)
    ) {
      toast.error("Choose a product, location, and valid quantity.");
      return;
    }
    if (isTransfer && !effectiveDestinationId) {
      toast.error("Choose a destination different from the source location.");
      return;
    }
    if (movementType === "adjustment" && !movementNote.trim()) {
      toast.error("Adjustments require a reason.");
      return;
    }

    setSubmitting(true);
    try {
      await recordMovement({
        productId: movementProductId,
        locationId: effectiveLocationId,
        type: movementType,
        quantity,
        note: movementNote,
        destinationLocationId: isTransfer ? effectiveDestinationId : undefined,
      });
      toast.success(isTransfer ? "Transfer recorded" : "Movement recorded");
      setMovementOpen(false);
      setMovementQuantity("");
      setMovementNote("");
    } catch (error) {
      showApiErrorToast(error);
    } finally {
      setSubmitting(false);
    }
  };

  const noProducts = products.length === 0;

  return (
    <>
      <PageHeader
        title="Inventory"
        description="Track on-hand stock and post receipts, sales, adjustments, and transfers."
        action={
          <>
            <Button
              variant="outline"
              onClick={() => setImportOpen(true)}
              disabled={noProducts}
            >
              <Upload />
              Import sales CSV
            </Button>
            <Button
              variant="outline"
              onClick={() => openMovement("transfer")}
              disabled={noProducts || locations.length < 2}
            >
              <ArrowRightLeft />
              Transfer
            </Button>
            <Button variant="outline" onClick={openSale} disabled={noProducts}>
              <ShoppingCart />
              Record sale
            </Button>
            <Button onClick={() => openMovement("receipt")} disabled={noProducts}>
              <ArrowDownUp />
              Record movement
            </Button>
          </>
        }
      />

      <Tabs defaultValue="stock">
        <TabsList>
          <TabsTrigger value="stock">Stock</TabsTrigger>
          <TabsTrigger value="history">Movement history</TabsTrigger>
        </TabsList>

        <TabsContent value="stock" className="mt-4">
          {stockLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : stockError ? (
            <LoadErrorState
              title="Could not load stock levels"
              message={stockError}
              onRetry={refreshStock}
            />
          ) : (
            <DataTable
              data={stockRows}
              columns={stockColumns}
              getRowId={(row) => row.id}
              searchValue={stockSearch}
              onSearchChange={setStockSearch}
              searchPlaceholder="Search by product or SKU…"
              toolbar={
                <>
                  <Select
                    value={locationFilter}
                    onValueChange={(value) => setLocationFilter(value ?? "all")}
                  >
                    <SelectTrigger className="w-44">
                      <SelectValue placeholder="Location" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All locations</SelectItem>
                      {locations.map((location) => (
                        <SelectItem key={location.id} value={location.id}>
                          {location.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    variant={lowStockOnly ? "default" : "outline"}
                    onClick={() => setLowStockOnly(!lowStockOnly)}
                  >
                    Low stock only
                  </Button>
                </>
              }
              emptyState={
                <EmptyState
                  icon={Warehouse}
                  title="No stock records"
                  message="Record a receipt to create your first on-hand balance."
                />
              }
            />
          )}
        </TabsContent>

        <TabsContent value="history" className="mt-4">
          {movementsLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : movementsError ? (
            <LoadErrorState
              title="Could not load movement history"
              message={movementsError}
              onRetry={refreshMovements}
            />
          ) : (
            <DataTable
              data={movements}
              columns={movementColumns}
              getRowId={(row) => row.id}
              pageSize={12}
              hideSearch
              toolbar={
                <Select
                  value={movementTypeFilter}
                  onValueChange={(value) =>
                    setMovementTypeFilter(value ?? "all")
                  }
                >
                  <SelectTrigger className="w-40">
                    <SelectValue placeholder="Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All types</SelectItem>
                    <SelectItem value="receipt">Receipt</SelectItem>
                    <SelectItem value="sale">Sale</SelectItem>
                    <SelectItem value="adjustment">Adjustment</SelectItem>
                    <SelectItem value="transfer">Transfer</SelectItem>
                  </SelectContent>
                </Select>
              }
              emptyState={
                <EmptyState
                  icon={ArrowDownUp}
                  title="No movements yet"
                  message="Record a receipt, sale, adjustment, or transfer to build history."
                />
              }
            />
          )}
        </TabsContent>
      </Tabs>

      <FormDialog
        open={movementOpen}
        onOpenChange={setMovementOpen}
        title={isTransfer ? "Transfer stock" : "Record movement"}
        description={
          isTransfer
            ? "Moves stock between locations as a paired ledger movement."
            : "Posts a ledger movement and refreshes on-hand stock."
        }
        submitLabel={
          submitting
            ? "Recording…"
            : isTransfer
              ? "Record transfer"
              : "Record movement"
        }
        isSubmitting={submitting}
        onSubmit={() => void submitMovement()}
      >
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Type</Label>
            <Select
              value={movementType}
              onValueChange={(value) =>
                setMovementType((value as ManualMovementType | null) ?? "receipt")
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="receipt">Receipt</SelectItem>
                <SelectItem value="adjustment">Adjustment</SelectItem>
                <SelectItem value="transfer" disabled={locations.length < 2}>
                  Transfer
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Product</Label>
            <Select
              value={movementProductId}
              onValueChange={(value) => setMovementProductId(value ?? "")}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select product" />
              </SelectTrigger>
              <SelectContent>
                {products.map((product) => (
                  <SelectItem key={product.id} value={product.id}>
                    {product.sku} — {product.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>{isTransfer ? "From location" : "Location"}</Label>
            <Select
              value={effectiveLocationId}
              onValueChange={(value) => setMovementLocationId(value ?? "")}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select location" />
              </SelectTrigger>
              <SelectContent>
                {locations.map((location) => (
                  <SelectItem key={location.id} value={location.id}>
                    {location.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {isTransfer ? (
            <div className="space-y-2">
              <Label>To location</Label>
              <Select
                value={effectiveDestinationId}
                onValueChange={(value) => setMovementDestinationId(value ?? "")}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select destination" />
                </SelectTrigger>
                <SelectContent>
                  {destinationOptions.map((location) => (
                    <SelectItem key={location.id} value={location.id}>
                      {location.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}
          <div className="space-y-2">
            <Label htmlFor="movement-quantity">Quantity</Label>
            <Input
              id="movement-quantity"
              inputMode="decimal"
              value={movementQuantity}
              onChange={(event) => setMovementQuantity(event.target.value)}
              placeholder={
                movementType === "adjustment"
                  ? "Use negative values to reduce stock"
                  : "Enter a positive quantity"
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="movement-note">
              {movementType === "adjustment" ? "Reason" : "Note"}
            </Label>
            <Input
              id="movement-note"
              value={movementNote}
              onChange={(event) => setMovementNote(event.target.value)}
              placeholder={
                movementType === "adjustment"
                  ? "Required for adjustments"
                  : "Optional"
              }
            />
          </div>
        </div>
      </FormDialog>

      <RecordSaleDialog
        key={saleDialogKey}
        open={saleOpen}
        onOpenChange={setSaleOpen}
        defaultLocationId={defaultLocationId}
      />

      <CsvImportDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        title="Import sales CSV"
        description="Each row posts a sale movement. Rows are processed in date order."
        sampleCsvPath={api.sales.sampleCsvHref}
        sampleFileName="sales-sample.csv"
        onImport={(file, options) => api.sales.importCsv(file, options)}
        onSuccess={async () => {
          await Promise.all([refreshStock(), refreshMovements()]);
        }}
      />
    </>
  );
}
