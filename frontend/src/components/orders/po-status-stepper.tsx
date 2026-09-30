import { StatusBadge } from "@/components/common/status-badge";
import type { PurchaseOrderStatus } from "@/types";
import { cn } from "@/lib/utils";

const steps: PurchaseOrderStatus[] = [
  "draft",
  "approved",
  "sent",
  "received",
];

interface PoStatusStepperProps {
  status: PurchaseOrderStatus;
}

export function PoStatusStepper({ status }: PoStatusStepperProps) {
  if (status === "cancelled") {
    return <StatusBadge variant="cancelled" />;
  }

  const activeIndex = steps.indexOf(status);

  return (
    <ol className="flex flex-wrap items-center gap-2">
      {steps.map((step, index) => {
        const complete = index <= activeIndex;
        return (
          <li key={step} className="flex items-center gap-2">
            <div
              className={cn(
                "flex size-7 items-center justify-center rounded-full border text-xs font-medium capitalize",
                complete
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-muted-foreground/30 text-muted-foreground",
              )}
            >
              {index + 1}
            </div>
            <span
              className={cn(
                "text-sm capitalize",
                complete ? "text-foreground" : "text-muted-foreground",
              )}
            >
              {step}
            </span>
            {index < steps.length - 1 ? (
              <span className="mx-1 hidden h-px w-6 bg-border sm:inline-block" />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
