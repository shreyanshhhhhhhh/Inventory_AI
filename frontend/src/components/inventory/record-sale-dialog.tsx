"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { FormDialog } from "@/components/common/form-dialog";
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
import { showApiErrorToast } from "@/lib/api";
import { useInventory } from "@/lib/inventory-hooks";

interface SaleLineDraft {
  id: number;
  productId: string;
  quantity: string;
}

interface RecordSaleDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultLocationId: string;
}

/** Mount with a fresh `key` per open so the draft starts empty. */
export function RecordSaleDialog({
  open,
  onOpenChange,
  defaultLocationId,
}: RecordSaleDialogProps) {
  const { products, locations, recordSale } = useInventory();
  const [locationId, setLocationId] = useState("");
  const [lines, setLines] = useState<SaleLineDraft[]>([
    { id: 1, productId: "", quantity: "" },
  ]);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const effectiveLocationId = locationId || defaultLocationId;

  const updateLine = (id: number, patch: Partial<Omit<SaleLineDraft, "id">>) => {
    setLines((current) =>
      current.map((line) => (line.id === id ? { ...line, ...patch } : line)),
    );
  };

  const addLine = () => {
    setLines((current) => [
      ...current,
      {
        id: Math.max(0, ...current.map((line) => line.id)) + 1,
        productId: "",
        quantity: "",
      },
    ]);
  };

  const removeLine = (id: number) => {
    setLines((current) =>
      current.length > 1 ? current.filter((line) => line.id !== id) : current,
    );
  };

  const submit = async () => {
    if (!effectiveLocationId) {
      toast.error("Choose a location.");
      return;
    }
    const parsed = lines.map((line) => ({
      productId: line.productId,
      quantity: Number(line.quantity),
    }));
    if (
      parsed.some(
        (line) =>
          !line.productId || !Number.isFinite(line.quantity) || line.quantity <= 0,
      )
    ) {
      toast.error("Each line needs a product and a positive quantity.");
      return;
    }
    const productIds = parsed.map((line) => line.productId);
    if (new Set(productIds).size !== productIds.length) {
      toast.error("Each product can appear only once per sale.");
      return;
    }

    setSubmitting(true);
    try {
      await recordSale({ locationId: effectiveLocationId, lines: parsed, note });
      toast.success(
        parsed.length === 1 ? "Sale recorded" : `Sale of ${parsed.length} lines recorded`,
      );
      onOpenChange(false);
    } catch (error) {
      showApiErrorToast(error);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <FormDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Record sale"
      description="Posts every line as one sale. Stock cannot go below zero."
      submitLabel={submitting ? "Recording…" : "Record sale"}
      isSubmitting={submitting}
      onSubmit={() => void submit()}
    >
      <div className="space-y-4">
        <div className="space-y-2">
          <Label>Location</Label>
          <Select
            value={effectiveLocationId}
            onValueChange={(value) => setLocationId(value ?? "")}
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

        <div className="space-y-3">
          <Label>Lines</Label>
          {lines.map((line) => {
            const takenElsewhere = new Set(
              lines
                .filter((other) => other.id !== line.id && other.productId)
                .map((other) => other.productId),
            );
            return (
              <div key={line.id} className="flex items-start gap-2">
                <div className="min-w-0 flex-1">
                  <Select
                    value={line.productId}
                    onValueChange={(value) =>
                      updateLine(line.id, { productId: value ?? "" })
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Product" />
                    </SelectTrigger>
                    <SelectContent>
                      {products
                        .filter((product) => !takenElsewhere.has(product.id))
                        .map((product) => (
                          <SelectItem key={product.id} value={product.id}>
                            {product.sku} — {product.name}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                </div>
                <Input
                  className="w-24"
                  inputMode="decimal"
                  placeholder="Qty"
                  aria-label="Quantity"
                  value={line.quantity}
                  onChange={(event) =>
                    updateLine(line.id, { quantity: event.target.value })
                  }
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label="Remove line"
                  disabled={lines.length === 1}
                  onClick={() => removeLine(line.id)}
                >
                  <Trash2 />
                </Button>
              </div>
            );
          })}
          <Button
            type="button"
            variant="outline"
            onClick={addLine}
            disabled={lines.length >= products.length}
          >
            <Plus />
            Add line
          </Button>
        </div>

        <div className="space-y-2">
          <Label htmlFor="sale-note">Note</Label>
          <Input
            id="sale-note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Optional"
          />
        </div>
      </div>
    </FormDialog>
  );
}
