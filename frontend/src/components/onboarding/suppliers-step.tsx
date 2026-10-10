"use client";

import { Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { CatalogCsvImport } from "@/components/onboarding/catalog-csv-import";
import { StepFooter, type StepNavigation } from "@/components/onboarding/step-footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { showApiErrorToast } from "@/lib/api";
import { useSuppliers } from "@/lib/catalog-hooks";

const emptySupplierForm = {
  name: "",
  email: "",
  phone: "",
  leadTimeDays: "",
};

interface SuppliersStepProps extends StepNavigation {
  onChanged: () => Promise<void>;
  onCatalogImported: () => Promise<void>;
}

export function SuppliersStep({
  onNext,
  onBack,
  onChanged,
  onCatalogImported,
}: SuppliersStepProps) {
  const { suppliers, isLoading, error, addSupplier } = useSuppliers();
  const activeSuppliers = suppliers.filter((supplier) => supplier.isActive);
  const [form, setForm] = useState(emptySupplierForm);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleAdd = async () => {
    const name = form.name.trim();
    const leadTime = form.leadTimeDays.trim();
    if (!name) {
      setFormError("Supplier name is required.");
      return;
    }
    if (leadTime && !/^\d+$/.test(leadTime)) {
      setFormError("Lead time must be a whole number of days.");
      return;
    }
    setFormError(null);
    setSubmitting(true);
    try {
      await addSupplier({
        name,
        email: form.email.trim(),
        phone: form.phone.trim(),
        leadTimeDays: leadTime ? Number(leadTime) : 0,
      });
      await onChanged();
      toast.success("Supplier added");
      setForm(emptySupplierForm);
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : activeSuppliers.length === 0 ? (
        <p className="rounded-md border border-dashed p-4 text-center text-sm text-muted-foreground">
          No suppliers yet. Add one below, import a catalog CSV with a supplier column, or load
          demo data in the next step.
        </p>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Phone</TableHead>
                <TableHead className="text-right">Lead time</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {activeSuppliers.map((supplier) => (
                <TableRow key={supplier.id}>
                  <TableCell className="font-medium">{supplier.name}</TableCell>
                  <TableCell>{supplier.email || "—"}</TableCell>
                  <TableCell>{supplier.phone || "—"}</TableCell>
                  <TableCell className="text-right">{supplier.leadTimeDays} days</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <form
        className="space-y-4 rounded-md border p-4"
        onSubmit={(event) => {
          event.preventDefault();
          void handleAdd();
        }}
      >
        <p className="text-sm font-medium">Add a supplier</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="onboarding-supplier-name">Name</Label>
            <Input
              id="onboarding-supplier-name"
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="onboarding-supplier-email">Email (optional)</Label>
            <Input
              id="onboarding-supplier-email"
              type="email"
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="onboarding-supplier-phone">Phone (optional)</Label>
            <Input
              id="onboarding-supplier-phone"
              value={form.phone}
              onChange={(event) => setForm({ ...form, phone: event.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="onboarding-supplier-lead-time">Lead time (days)</Label>
            <Input
              id="onboarding-supplier-lead-time"
              inputMode="numeric"
              placeholder="0"
              value={form.leadTimeDays}
              onChange={(event) => setForm({ ...form, leadTimeDays: event.target.value })}
            />
          </div>
        </div>
        {formError ? <p className="text-xs text-destructive">{formError}</p> : null}
        <div className="flex justify-end">
          <Button type="submit" variant="secondary" disabled={submitting}>
            <Plus />
            {submitting ? "Adding…" : "Add supplier"}
          </Button>
        </div>
      </form>

      <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-4">
        <p className="text-sm text-muted-foreground">
          Already have a spreadsheet? A catalog CSV with a supplier column creates suppliers and
          products together.
        </p>
        <CatalogCsvImport label="Import catalog CSV" onImported={onCatalogImported} />
      </div>

      <StepFooter
        onBack={onBack}
        onNext={onNext}
        hint={
          activeSuppliers.length === 0
            ? "You can continue without a supplier if you plan to load demo data or import a CSV next. At least one supplier is needed to finish."
            : undefined
        }
      />
    </div>
  );
}
