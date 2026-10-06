"use client";

import {
  AlertTriangle,
  BarChart3,
  Check,
  LoaderCircle,
  Mail,
  Package,
  Shield,
  SkipForward,
  Sparkles,
  Truck,
  X,
} from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import type { PlanState, PlanStep } from "@/lib/chat/types";
import { cn } from "@/lib/utils";

const AGENT_ICON = {
  forecast: BarChart3,
  exception_monitor: AlertTriangle,
  replenishment: Package,
  supplier_comm: Mail,
  explainer: Sparkles,
  data_quality: Shield,
  guardrail: Shield,
} as const;

function StepIcon({ step }: { step: PlanStep }) {
  if (step.status === "running") {
    return <LoaderCircle className="size-3.5 animate-spin text-primary" />;
  }
  if (step.status === "completed") {
    return <Check className="size-3.5 text-emerald-600 dark:text-emerald-400" />;
  }
  if (step.status === "failed") {
    return <X className="size-3.5 text-destructive" />;
  }
  if (step.status === "skipped") {
    return <SkipForward className="size-3.5 text-muted-foreground" />;
  }
  const Icon = AGENT_ICON[step.agent as keyof typeof AGENT_ICON] ?? Sparkles;
  return <Icon className="size-3.5 text-muted-foreground" />;
}

function formatDuration(ms: number | null): string | null {
  if (ms === null) return null;
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function PlanCard({
  plan,
  collapsed,
  onRun,
  onCancel,
  onEdit,
}: {
  plan: PlanState;
  collapsed?: boolean;
  onRun?: () => void;
  onCancel?: () => void;
  onEdit?: (plan: PlanState) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [dropped, setDropped] = useState<string[]>([]);
  const visible = plan.steps.filter((step) => step.agent !== "guardrail");

  function submitEdit() {
    const steps = plan.steps.filter((step) => !dropped.includes(step.id));
    onEdit?.({ ...plan, steps });
    setEditing(false);
  }

  return (
    <section className="rounded-xl border bg-card p-3 shadow-sm transition-colors">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium">Plan</h3>
        {collapsed ? (
          <p className="text-xs text-muted-foreground">{visible.length} steps</p>
        ) : null}
      </div>
      <ol className={cn("mt-2 space-y-1.5", collapsed && "hidden md:block")}>
        {visible.map((step) => (
          <li key={step.id} className="flex items-start gap-2 rounded-lg px-1 py-1">
            {editing ? (
              <input
                type="checkbox"
                className="mt-1"
                checked={!dropped.includes(step.id)}
                onChange={() =>
                  setDropped((current) =>
                    current.includes(step.id)
                      ? current.filter((id) => id !== step.id)
                      : [...current, step.id],
                  )
                }
                aria-label={`Keep ${step.agent} ${step.task}`}
              />
            ) : (
              <span className="mt-0.5">
                <StepIcon step={step} />
              </span>
            )}
            <div className="min-w-0 flex-1">
              <p className="text-sm">
                <span className="font-medium">{step.agent}</span>
                <span className="text-muted-foreground"> · {step.task}</span>
              </p>
              {step.status === "failed" && step.error ? (
                <p className="text-xs text-destructive">{step.error}</p>
              ) : null}
              {step.status === "completed" && step.durationMs !== null ? (
                <p className="text-xs text-muted-foreground">{formatDuration(step.durationMs)}</p>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
      {plan.awaitingApproval ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {editing ? (
            <>
              <Button size="sm" onClick={submitEdit}>
                Save and run
              </Button>
              <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
                Back
              </Button>
            </>
          ) : (
            <>
              <Button size="sm" onClick={onRun}>
                Run
              </Button>
              <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
                Edit
              </Button>
              <Button size="sm" variant="destructive" onClick={onCancel}>
                Cancel
              </Button>
            </>
          )}
        </div>
      ) : null}
    </section>
  );
}
