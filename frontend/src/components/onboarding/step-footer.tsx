"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

export interface StepNavigation {
  onBack?: () => void;
  onNext?: () => void;
}

interface StepFooterProps extends StepNavigation {
  nextLabel?: string;
  nextDisabled?: boolean;
  nextBusy?: boolean;
  hint?: ReactNode;
}

export function StepFooter({
  onBack,
  onNext,
  nextLabel = "Next",
  nextDisabled = false,
  nextBusy = false,
  hint,
}: StepFooterProps) {
  return (
    <div className="space-y-4 pt-2">
      <Separator />
      {hint ? <p className="text-sm text-muted-foreground">{hint}</p> : null}
      <div className="flex items-center justify-between gap-2">
        {onBack ? (
          <Button type="button" variant="outline" onClick={onBack}>
            <ChevronLeft />
            Back
          </Button>
        ) : (
          <span />
        )}
        {onNext ? (
          <Button
            type="button"
            onClick={onNext}
            disabled={nextDisabled || nextBusy}
          >
            {nextBusy ? "Saving…" : nextLabel}
            <ChevronRight />
          </Button>
        ) : null}
      </div>
    </div>
  );
}
