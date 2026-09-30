import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type StatusBadgeVariant =
  | "in-stock"
  | "low"
  | "out"
  | "draft"
  | "approved"
  | "sent"
  | "received"
  | "cancelled"
  | "severity-low"
  | "severity-medium"
  | "severity-high";

const variantStyles: Record<StatusBadgeVariant, string> = {
  "in-stock":
    "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300",
  low: "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300",
  out: "border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300",
  draft:
    "border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300",
  approved:
    "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-300",
  sent: "border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-900 dark:bg-violet-950 dark:text-violet-300",
  received:
    "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300",
  cancelled:
    "border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300",
  "severity-low":
    "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900 dark:bg-sky-950 dark:text-sky-300",
  "severity-medium":
    "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300",
  "severity-high":
    "border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300",
};

const variantLabels: Record<StatusBadgeVariant, string> = {
  "in-stock": "In stock",
  low: "Low",
  out: "Out",
  draft: "Draft",
  approved: "Approved",
  sent: "Sent",
  received: "Received",
  cancelled: "Cancelled",
  "severity-low": "Low",
  "severity-medium": "Medium",
  "severity-high": "High",
};

interface StatusBadgeProps {
  variant: StatusBadgeVariant;
  label?: string;
}

export function StatusBadge({ variant, label }: StatusBadgeProps) {
  return (
    <Badge
      variant="outline"
      className={cn("rounded-full font-medium", variantStyles[variant])}
    >
      {label ?? variantLabels[variant]}
    </Badge>
  );
}
