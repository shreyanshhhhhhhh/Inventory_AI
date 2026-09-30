"use client";

import { DataTable, type DataTableColumn } from "@/components/common/data-table";
import { PageHeader } from "@/components/common/page-header";
import { StatCard } from "@/components/common/stat-card";
import { StatusBadge } from "@/components/common/status-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency } from "@/lib/format";
import { useReports, type SupplierPayableRow } from "@/lib/reports-hooks";

export function AccountsPageContent() {
  const {
    stockValue,
    openPoValue,
    payablesDue,
    supplierRows,
    isLoading,
    error,
  } = useReports();

  const columns: DataTableColumn<SupplierPayableRow>[] = [
    { id: "supplier", header: "Supplier", cell: (row) => row.supplierName },
    {
      id: "status",
      header: "Status",
      cell: (row) => <StatusBadge variant={row.status} />,
    },
    {
      id: "amount",
      header: "Total",
      cell: (row) => formatCurrency(row.total),
    },
    {
      id: "count",
      header: "POs",
      cell: (row) => String(row.purchaseOrderCount),
    },
  ];

  if (isLoading) {
    return (
      <>
        <PageHeader
          title="Accounts"
          description="Lite financial snapshot from inventory and open purchase orders."
        />
        <div className="grid gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-28 w-full" />
          ))}
        </div>
        <Skeleton className="h-64 w-full" />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Accounts"
        description="Lite financial snapshot from inventory and open purchase orders."
      />

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Stock value"
          value={formatCurrency(stockValue)}
          subtext="On-hand × unit cost"
        />
        <StatCard
          label="Open PO value"
          value={formatCurrency(openPoValue)}
          subtext="Draft, approved, and sent"
        />
        <StatCard
          label="Payables due"
          value={formatCurrency(payablesDue)}
          subtext="Approved or sent, not yet received"
        />
      </div>

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
    </>
  );
}
