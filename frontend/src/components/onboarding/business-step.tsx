"use client";

import { useState } from "react";
import { toast } from "sonner";

import { StepFooter, type StepNavigation } from "@/components/onboarding/step-footer";
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
import { useAuth } from "@/lib/auth-context";
import { useSettings } from "@/lib/settings-hooks";

const COMMON_CURRENCIES: { code: string; label: string }[] = [
  { code: "USD", label: "US dollar" },
  { code: "EUR", label: "Euro" },
  { code: "GBP", label: "British pound" },
  { code: "INR", label: "Indian rupee" },
  { code: "CAD", label: "Canadian dollar" },
  { code: "AUD", label: "Australian dollar" },
  { code: "JPY", label: "Japanese yen" },
  { code: "SGD", label: "Singapore dollar" },
  { code: "AED", label: "UAE dirham" },
];

interface BusinessStepProps extends StepNavigation {
  onChanged: () => Promise<void>;
}

export function BusinessStep({ onNext, onBack, onChanged }: BusinessStepProps) {
  const { business } = useAuth();
  const { saveBusinessProfile } = useSettings();
  const savedName = business?.name ?? "";
  const savedCurrency = business?.currency_code ?? "USD";
  const [name, setName] = useState(savedName);
  const [currency, setCurrency] = useState(savedCurrency);
  const [nameError, setNameError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const currencyOptions = COMMON_CURRENCIES.some((item) => item.code === savedCurrency)
    ? COMMON_CURRENCIES
    : [{ code: savedCurrency, label: "Current" }, ...COMMON_CURRENCIES];

  const handleNext = async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setNameError("Business name is required.");
      return;
    }
    setNameError(null);
    if (trimmed === savedName && currency === savedCurrency) {
      onNext?.();
      return;
    }
    setSaving(true);
    try {
      await saveBusinessProfile({ name: trimmed, currencyCode: currency });
      await onChanged();
      toast.success("Business details saved");
      onNext?.();
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form
      className="space-y-6"
      onSubmit={(event) => {
        event.preventDefault();
        void handleNext();
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="onboarding-business-name">Business name</Label>
          <Input
            id="onboarding-business-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            aria-invalid={Boolean(nameError)}
          />
          {nameError ? <p className="text-xs text-destructive">{nameError}</p> : null}
        </div>
        <div className="space-y-2">
          <Label>Currency</Label>
          <Select
            value={currency}
            onValueChange={(value) => setCurrency(value ?? savedCurrency)}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {currencyOptions.map((item) => (
                <SelectItem key={item.code} value={item.code}>
                  {item.code} · {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <p className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
        Pick carefully: the currency is locked once setup is finished. Prices and costs are
        stored without conversion, so it cannot be changed later.
      </p>
      <StepFooter
        onBack={onBack}
        onNext={() => void handleNext()}
        nextLabel="Save and continue"
        nextBusy={saving}
      />
    </form>
  );
}
