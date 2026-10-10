"use client";

import { DataTable, type DataTableColumn } from "@/components/common/data-table";
import { StatCard } from "@/components/common/stat-card";
import { StatusBadge } from "@/components/common/status-badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency } from "@/lib/format";
import { useReports, type SupplierPayableRow } from "@/lib/reports-hooks";

const columns: DataTableColumn<SupplierPayableRow>[] = [
  { id: "supplier", header: "Supplier", cell: (row) => row.supplierName },
  {
    id: "status",
    header: "Status",
    cell: (row) => <StatusBadge variant={row.status} />,
  },
  {
    id: "amount",
    header: "PO total",
    cell: (row) => formatCurrency(row.total),
  },
  {
    id: "count",
    header: "POs",
    cell: (row) => String(row.purchaseOrderCount),
  },
];

export function SpendSnapshotTab() {
  const {
    stockValue,
    unvaluedProductCount,
    openPoValue,
    payablesDue,
    supplierRows,
    isLoading,
    error,
    refresh,
  } = useReports();

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-28 w-full" />
          ))}
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-start gap-3 rounded-lg border border-destructive/40 p-4">
        <p className="text-sm text-destructive">{error}</p>
        <Button variant="outline" size="sm" onClick={() => void refresh()}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Operational snapshot from current stock and purchase orders. This is not
        an accounting ledger.
      </p>

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Stock value"
          value={formatCurrency(stockValue)}
          subtext="On-hand × preferred-supplier cost"
        />
        <StatCard
          label="Open PO value"
          value={formatCurrency(openPoValue)}
          subtext="Draft, approved, and sent"
        />
        <StatCard
          label="Awaiting receipt"
          value={formatCurrency(payablesDue)}
          subtext="Approved or sent, not yet received"
        />
      </div>

      {unvaluedProductCount > 0 ? (
        <p className="text-xs text-muted-foreground">
          {unvaluedProductCount === 1
            ? "1 product has no preferred-supplier cost and is excluded from stock value."
            : `${unvaluedProductCount} products have no preferred-supplier cost and are excluded from stock value.`}
        </p>
      ) : null}

      <div className="space-y-2">
        <h3 className="text-sm font-medium">PO spend by supplier</h3>
        <DataTable
          data={supplierRows}
          columns={columns}
          getRowId={(row) => row.id}
          searchPlaceholder="Search supplier…"
          pageSize={8}
          emptyState={
            <p className="py-8 text-center text-sm text-muted-foreground">
              No purchase order totals yet.
            </p>
          }
        />
      </div>
    </div>
  );
}
