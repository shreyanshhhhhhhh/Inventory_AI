"use client";

import { Check, LogOut } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { BusinessStep } from "@/components/onboarding/business-step";
import { LocationsStep } from "@/components/onboarding/locations-step";
import { ProductsStep } from "@/components/onboarding/products-step";
import { ReviewStep } from "@/components/onboarding/review-step";
import { SuppliersStep } from "@/components/onboarding/suppliers-step";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type { ApiOnboardingStatus } from "@/lib/api-types";
import { useAuth } from "@/lib/auth-context";
import { useProducts, useSuppliers } from "@/lib/catalog-hooks";
import { useInventory } from "@/lib/inventory-hooks";
import { errorMessage, type LoadResult } from "@/lib/load-result";
import { usePurchaseOrders } from "@/lib/purchase-orders-hooks";
import { useSettings } from "@/lib/settings-hooks";
import { cn } from "@/lib/utils";

const STEPS = [
  {
    title: "Business",
    description: "Name your business and choose the currency for prices and costs.",
  },
  {
    title: "Locations",
    description: "Where do you keep stock? You need at least one location.",
  },
  {
    title: "Suppliers",
    description: "Who do you buy from? Suppliers are linked to products and purchase orders.",
  },
  {
    title: "Products",
    description: "Build your catalog by hand, from a CSV, or start with demo data.",
  },
  {
    title: "Review",
    description: "Check everything is in place, then finish setup.",
  },
] as const;

const LAST_STEP = STEPS.length - 1;

async function fetchOnboardingStatus(): Promise<LoadResult<ApiOnboardingStatus>> {
  try {
    return { data: await api.onboarding.status(), error: null };
  } catch (err) {
    return { data: null, error: errorMessage(err, "Could not load setup progress.") };
  }
}

function isStepComplete(
  index: number,
  status: ApiOnboardingStatus | null,
  furthestStep: number,
): boolean {
  switch (index) {
    case 0:
      return furthestStep > 0;
    case 1:
      return (status?.location_count ?? 0) > 0;
    case 2:
      return (status?.supplier_count ?? 0) > 0;
    case 3:
      return (status?.product_count ?? 0) > 0;
    default:
      return status?.can_complete ?? false;
  }
}

export function OnboardingWizard() {
  const { user, logout } = useAuth();
  const { refresh: refreshProducts } = useProducts();
  const { refresh: refreshSuppliers } = useSuppliers();
  const { refresh: refreshSettings } = useSettings();
  const { refreshStock, refreshMovements } = useInventory();
  const { refreshPurchaseOrders } = usePurchaseOrders();

  const [stepIndex, setStepIndex] = useState(0);
  const [furthestStep, setFurthestStep] = useState(0);
  const [status, setStatus] = useState<ApiOnboardingStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [statusError, setStatusError] = useState<string | null>(null);

  const applyStatus = useCallback((result: LoadResult<ApiOnboardingStatus>) => {
    if (result.data) setStatus(result.data);
    setStatusError(result.error);
    setStatusLoading(false);
  }, []);

  const refreshStatus = useCallback(async () => {
    applyStatus(await fetchOnboardingStatus());
  }, [applyStatus]);

  useEffect(() => {
    let cancelled = false;
    void fetchOnboardingStatus().then((result) => {
      if (!cancelled) applyStatus(result);
    });
    return () => {
      cancelled = true;
    };
  }, [applyStatus]);

  const refreshAfterCatalogImport = useCallback(async () => {
    await Promise.all([
      refreshProducts(),
      refreshSuppliers(),
      refreshSettings(),
      refreshStock(),
      refreshMovements(),
      refreshPurchaseOrders(),
      refreshStatus(),
    ]);
  }, [
    refreshProducts,
    refreshSuppliers,
    refreshSettings,
    refreshStock,
    refreshMovements,
    refreshPurchaseOrders,
    refreshStatus,
  ]);

  const goToStep = (index: number) => {
    const next = Math.min(Math.max(index, 0), LAST_STEP);
    setStepIndex(next);
    setFurthestStep((current) => Math.max(current, next));
    void refreshStatus();
  };

  const retryStatus = () => {
    setStatusLoading(true);
    void refreshStatus();
  };

  const navigation = {
    onBack: stepIndex > 0 ? () => goToStep(stepIndex - 1) : undefined,
    onNext: stepIndex < LAST_STEP ? () => goToStep(stepIndex + 1) : undefined,
  };
  const currentStep = STEPS[stepIndex];

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-4 sm:p-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm text-muted-foreground">
            Welcome{user?.full_name ? `, ${user.full_name}` : ""}
          </p>
          <h1 className="text-2xl font-semibold tracking-tight">Set up your business</h1>
          <p className="text-sm text-muted-foreground">
            A few steps before you can open the dashboard.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => void logout()}>
          <LogOut />
          Sign out
        </Button>
      </header>

      <nav aria-label="Setup steps">
        <ol className="grid grid-cols-5 gap-2">
          {STEPS.map((step, index) => {
            const complete = isStepComplete(index, status, furthestStep);
            const active = index === stepIndex;
            return (
              <li key={step.title}>
                <button
                  type="button"
                  onClick={() => goToStep(index)}
                  aria-current={active ? "step" : undefined}
                  className={cn(
                    "flex w-full flex-col items-center gap-1 rounded-md p-2 text-xs transition-colors hover:bg-muted sm:flex-row sm:text-sm",
                    active && "bg-muted font-medium",
                  )}
                >
                  <span
                    className={cn(
                      "flex size-6 shrink-0 items-center justify-center rounded-full border text-xs",
                      complete && "border-primary bg-primary text-primary-foreground",
                      active && !complete && "border-primary text-primary",
                    )}
                  >
                    {complete ? <Check className="size-3.5" /> : index + 1}
                  </span>
                  <span className="truncate">{step.title}</span>
                </button>
              </li>
            );
          })}
        </ol>
      </nav>

      {statusLoading && !status ? (
        <Skeleton className="h-5 w-72" />
      ) : statusError ? (
        <div className="flex flex-wrap items-center gap-2 text-sm text-destructive">
          <span>{statusError}</span>
          <Button variant="outline" size="sm" onClick={retryStatus}>
            Retry
          </Button>
        </div>
      ) : status ? (
        <p className="text-sm text-muted-foreground">
          {status.location_count} location{status.location_count === 1 ? "" : "s"} ·{" "}
          {status.supplier_count} supplier{status.supplier_count === 1 ? "" : "s"} ·{" "}
          {status.product_count} product{status.product_count === 1 ? "" : "s"}
        </p>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>
            Step {stepIndex + 1} of {STEPS.length}: {currentStep.title}
          </CardTitle>
          <CardDescription>{currentStep.description}</CardDescription>
        </CardHeader>
        <CardContent>
          {stepIndex === 0 ? (
            <BusinessStep {...navigation} onChanged={refreshStatus} />
          ) : stepIndex === 1 ? (
            <LocationsStep {...navigation} onChanged={refreshStatus} />
          ) : stepIndex === 2 ? (
            <SuppliersStep
              {...navigation}
              onChanged={refreshStatus}
              onCatalogImported={refreshAfterCatalogImport}
            />
          ) : stepIndex === 3 ? (
            <ProductsStep
              {...navigation}
              status={status}
              onChanged={refreshStatus}
              onCatalogImported={refreshAfterCatalogImport}
            />
          ) : (
            <ReviewStep
              {...navigation}
              status={status}
              onChanged={refreshStatus}
              onGoToStep={goToStep}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
