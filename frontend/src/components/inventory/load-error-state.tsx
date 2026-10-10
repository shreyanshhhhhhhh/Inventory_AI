"use client";

import { AlertTriangle, RotateCw } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";

interface LoadErrorStateProps {
  title?: string;
  message: string;
  onRetry: () => Promise<void> | void;
}

export function LoadErrorState({
  title = "Could not load data",
  message,
  onRetry,
}: LoadErrorStateProps) {
  const [retrying, setRetrying] = useState(false);

  const retry = async () => {
    setRetrying(true);
    try {
      await onRetry();
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center rounded-xl border border-destructive/30 bg-destructive/5 px-6 py-12 text-center"
    >
      <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-destructive/10">
        <AlertTriangle className="size-6 text-destructive" />
      </div>
      <h3 className="text-base font-medium">{title}</h3>
      <p className="mt-1 max-w-md text-sm text-muted-foreground">{message}</p>
      <Button
        className="mt-4"
        variant="outline"
        disabled={retrying}
        onClick={() => void retry()}
      >
        <RotateCw />
        {retrying ? "Retrying…" : "Retry"}
      </Button>
    </div>
  );
}
