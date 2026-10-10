"use client";

import { CheckCircle2, Circle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { StepFooter, type StepNavigation } from "@/components/onboarding/step-footer";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError, showApiErrorToast } from "@/lib/api";
import type { ApiOnboardingStatus } from "@/lib/api-types";
import { useAuth } from "@/lib/auth-context";

interface ReviewStepProps extends StepNavigation {
  status: ApiOnboardingStatus | null;
  onChanged: () => Promise<void>;
  onGoToStep: (index: number) => void;
}

export function ReviewStep({ status, onBack, onChanged, onGoToStep }: ReviewStepProps) {
  const { refreshSession } = useAuth();
  const router = useRouter();
  const [finishing, setFinishing] = useState(false);
  const [finishError, setFinishError] = useState<string | null>(null);

  if (!status) {
    return <Skeleton className="h-48 w-full" />;
  }

  const requirements = [
    { label: "Locations", count: status.location_count, step: 1 },
    { label: "Suppliers", count: status.supplier_count, step: 2 },
    { label: "Products", count: status.product_count, step: 3 },
  ];

  const handleFinish = async () => {
    setFinishing(true);
    setFinishError(null);
    try {
      await api.onboarding.complete();
      await refreshSession();
      toast.success("Setup complete");
      router.replace("/");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setFinishError(err.message);
        await onChanged();
      } else {
        showApiErrorToast(err);
      }
      setFinishing(false);
    }
  };

  return (
    <div className="space-y-6">
      <dl className="grid gap-3 rounded-md border p-4 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-muted-foreground">Business</dt>
          <dd className="font-medium">{status.business_name}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Currency</dt>
          <dd className="font-medium">
            {status.currency_code}{" "}
            <span className="font-normal text-muted-foreground">(locked after setup)</span>
          </dd>
        </div>
      </dl>

      <ul className="divide-y rounded-md border">
        {requirements.map((item) => {
          const done = item.count > 0;
          return (
            <li key={item.label} className="flex items-center justify-between gap-2 p-3">
              <span className="flex items-center gap-2">
                {done ? (
                  <CheckCircle2 className="size-4 text-emerald-600" />
                ) : (
                  <Circle className="size-4 text-muted-foreground" />
                )}
                <span className="font-medium">{item.label}</span>
                <span className="text-muted-foreground">{item.count}</span>
              </span>
              {done ? null : (
                <Button variant="link" size="sm" onClick={() => onGoToStep(item.step)}>
                  Add {item.label.toLowerCase()}
                </Button>
              )}
            </li>
          );
        })}
      </ul>

      {finishError ? (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {finishError}
        </p>
      ) : null}

      <StepFooter
        onBack={onBack}
        onNext={() => void handleFinish()}
        nextLabel={finishing ? "Finishing…" : "Finish setup"}
        nextDisabled={!status.can_complete || finishing}
        hint={
          status.can_complete
            ? "Finishing locks the currency and opens the dashboard."
            : "You need at least one location, one supplier, and one product to finish."
        }
      />
    </div>
  );
}
