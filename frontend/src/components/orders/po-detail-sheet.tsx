"use client";

import { StatusBadge } from "@/components/common/status-badge";
import { PoStatusStepper } from "@/components/orders/po-status-stepper";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatCurrency, formatDate } from "@/lib/format";
import type { PurchaseOrder } from "@/types";

type TransitionAction = "approve" | "send" | "receive" | "cancel";

interface PoDetailSheetProps {
  order: PurchaseOrder | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  supplierName: string;
  getProductName: (productId: string) => string;
  total: number;
  onTransition: (action: TransitionAction) => void;
  isSubmitting?: boolean;
  /** Only owners may approve; staff see a waiting note on drafts. */
  canApprove: boolean;
}

export function PoDetailSheet({
  order,
  open,
  onOpenChange,
  supplierName,
  getProductName,
  total,
  onTransition,
  isSubmitting = false,
  canApprove,
}: PoDetailSheetProps) {
  if (!order) return null;

  const nextActions: Partial<
    Record<PurchaseOrder["status"], { label: string; action: TransitionAction }>
  > = {
    draft: { label: "Approve", action: "approve" },
    approved: { label: "Mark sent", action: "send" },
    sent: { label: "Receive", action: "receive" },
  };

  const candidate = nextActions[order.status];
  const awaitingOwnerApproval = candidate?.action === "approve" && !canApprove;
  const action = awaitingOwnerApproval ? undefined : candidate;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{order.poNumber}</SheetTitle>
          <SheetDescription>
            {supplierName}
            {order.expectedDate
              ? ` · Expected ${formatDate(order.expectedDate)}`
              : ""}
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-6 px-4 pb-6">
          <div className="flex items-center gap-2">
            <StatusBadge variant={order.status} />
          </div>

          <PoStatusStepper status={order.status} />

          <div className="overflow-hidden rounded-xl border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead>Qty</TableHead>
                  <TableHead>Unit cost</TableHead>
                  <TableHead>Line total</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {order.lineItems.map((line) => (
                  <TableRow key={line.id}>
                    <TableCell>{getProductName(line.productId)}</TableCell>
                    <TableCell>{line.quantity}</TableCell>
                    <TableCell>{formatCurrency(line.unitCost)}</TableCell>
                    <TableCell>
                      {formatCurrency(line.quantity * line.unitCost)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Order total</span>
            <span className="text-lg font-semibold">{formatCurrency(total)}</span>
          </div>

          {awaitingOwnerApproval ? (
            <p className="text-sm text-muted-foreground">
              Waiting for an owner to approve this purchase order.
            </p>
          ) : null}

          <div className="flex flex-wrap gap-2">
            {action ? (
              <Button
                disabled={isSubmitting}
                onClick={() => onTransition(action.action)}
              >
                {action.label}
              </Button>
            ) : null}
            {order.status !== "cancelled" && order.status !== "received" ? (
              <Button
                variant="outline"
                disabled={isSubmitting}
                onClick={() => onTransition("cancel")}
              >
                Cancel
              </Button>
            ) : null}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
