"use client";

import { Plus, Truck } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { DataTable, type DataTableColumn } from "@/components/common/data-table";
import { EmptyState } from "@/components/common/empty-state";
import { FormDialog } from "@/components/common/form-dialog";
import { LoadErrorState } from "@/components/inventory/load-error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { showApiErrorToast } from "@/lib/api";
import { useSuppliers } from "@/lib/catalog-hooks";
import type { Supplier } from "@/types";

const emptySupplierForm = {
  name: "",
  email: "",
  phone: "",
  leadTimeDays: "",
};

export function SuppliersTabContent() {
  const {
    suppliers,
    isLoading,
    error,
    refresh,
    addSupplier,
    updateSupplier,
    restoreSupplier,
    includeArchived,
    setIncludeArchived,
  } = useSuppliers();
  const [supplierDialogOpen, setSupplierDialogOpen] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState<Supplier | null>(null);
  const [supplierForm, setSupplierForm] = useState(emptySupplierForm);
  const [submitting, setSubmitting] = useState(false);
  const [restoringId, setRestoringId] = useState<string | null>(null);

  const handleRestore = async (supplier: Supplier) => {
    setRestoringId(supplier.id);
    try {
      await restoreSupplier(supplier.id);
      toast.success(`${supplier.name} restored`);
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setRestoringId(null);
    }
  };

  const supplierColumns: DataTableColumn<Supplier>[] = [
    {
      id: "name",
      header: "Name",
      cell: (row) => (
        <span className="flex items-center gap-2">
          {row.name}
          {!row.isActive ? <Badge variant="secondary">Archived</Badge> : null}
        </span>
      ),
    },
    { id: "email", header: "Email", cell: (row) => row.email || "—" },
    { id: "phone", header: "Phone", cell: (row) => row.phone || "—" },
    {
      id: "leadTimeDays",
      header: "Lead time",
      cell: (row) => `${row.leadTimeDays} days`,
    },
    {
      id: "actions",
      header: "",
      className: "text-right",
      cell: (row) =>
        row.isActive ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setEditingSupplier(row);
              setSupplierForm({
                name: row.name,
                email: row.email,
                phone: row.phone,
                leadTimeDays: String(row.leadTimeDays),
              });
              setSupplierDialogOpen(true);
            }}
          >
            Edit
          </Button>
        ) : (
          <Button
            variant="outline"
            size="sm"
            disabled={restoringId === row.id}
            onClick={() => void handleRestore(row)}
          >
            {restoringId === row.id ? "Restoring…" : "Restore"}
          </Button>
        ),
    },
  ];

  const submitSupplier = async () => {
    if (!supplierForm.name.trim() || !supplierForm.email.trim()) {
      toast.error("Name and email are required.");
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        name: supplierForm.name.trim(),
        email: supplierForm.email.trim(),
        phone: supplierForm.phone.trim(),
        leadTimeDays: Number(supplierForm.leadTimeDays) || 0,
      };
      if (editingSupplier) {
        await updateSupplier(editingSupplier.id, payload);
        toast.success("Supplier updated");
      } else {
        await addSupplier(payload);
        toast.success("Supplier added");
      }
      setSupplierDialogOpen(false);
      setEditingSupplier(null);
      setSupplierForm(emptySupplierForm);
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="ml-auto h-8 w-32" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <>
      <div className="space-y-4">
        <div className="flex justify-end gap-2">
          <Button
            variant={includeArchived ? "default" : "outline"}
            onClick={() => setIncludeArchived(!includeArchived)}
          >
            Show archived
          </Button>
          <Button
            onClick={() => {
              setEditingSupplier(null);
              setSupplierForm(emptySupplierForm);
              setSupplierDialogOpen(true);
            }}
          >
            <Plus />
            Add supplier
          </Button>
        </div>
        {error ? (
          <LoadErrorState
            title="Could not load suppliers"
            message={error}
            onRetry={refresh}
          />
        ) : (
          <DataTable
            data={suppliers}
            columns={supplierColumns}
            getRowId={(row) => row.id}
            emptyState={
              <EmptyState
                icon={Truck}
                title="No suppliers"
                message="Add suppliers to link products and purchase orders."
              />
            }
          />
        )}
      </div>

      <FormDialog
        open={supplierDialogOpen}
        onOpenChange={setSupplierDialogOpen}
        title={editingSupplier ? "Edit supplier" : "Add supplier"}
        submitLabel={editingSupplier ? "Save changes" : "Add supplier"}
        isSubmitting={submitting}
        onSubmit={() => void submitSupplier()}
      >
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="supplier-name">Name</Label>
            <Input
              id="supplier-name"
              value={supplierForm.name}
              onChange={(event) =>
                setSupplierForm({ ...supplierForm, name: event.target.value })
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="supplier-email">Email</Label>
            <Input
              id="supplier-email"
              type="email"
              value={supplierForm.email}
              onChange={(event) =>
                setSupplierForm({ ...supplierForm, email: event.target.value })
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="supplier-phone">Phone</Label>
            <Input
              id="supplier-phone"
              value={supplierForm.phone}
              onChange={(event) =>
                setSupplierForm({ ...supplierForm, phone: event.target.value })
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="supplier-lead-time">Lead time (days)</Label>
            <Input
              id="supplier-lead-time"
              inputMode="numeric"
              value={supplierForm.leadTimeDays}
              onChange={(event) =>
                setSupplierForm({
                  ...supplierForm,
                  leadTimeDays: event.target.value,
                })
              }
            />
          </div>
        </div>
      </FormDialog>
    </>
  );
}
