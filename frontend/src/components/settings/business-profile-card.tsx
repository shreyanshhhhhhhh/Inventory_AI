"use client";

import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { showApiErrorToast } from "@/lib/api";

interface BusinessProfileCardProps {
  initialName: string;
  initialCurrencyCode: string;
  currencyLocked: boolean;
  onSave: (input: { name: string; currencyCode: string }) => Promise<void>;
}

export function BusinessProfileCard({
  initialName,
  initialCurrencyCode,
  currencyLocked,
  onSave,
}: BusinessProfileCardProps) {
  const [name, setName] = useState(initialName);
  const [currencyCode, setCurrencyCode] = useState(initialCurrencyCode);
  const [saving, setSaving] = useState(false);

  const trimmedName = name.trim();
  const normalizedCurrency = currencyCode.trim().toUpperCase();
  const dirty =
    trimmedName !== initialName ||
    (!currencyLocked && normalizedCurrency !== initialCurrencyCode);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!trimmedName) {
      toast.error("Business name is required.");
      return;
    }
    if (!currencyLocked && !/^[A-Z]{3}$/.test(normalizedCurrency)) {
      toast.error("Currency must be a 3-letter code, e.g. USD.");
      return;
    }
    setSaving(true);
    try {
      await onSave({ name: trimmedName, currencyCode: normalizedCurrency });
      toast.success("Business profile saved");
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Business profile</CardTitle>
        <CardDescription>Name and currency for this business.</CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={(event) => void handleSubmit(event)}>
          <div className="space-y-2">
            <Label htmlFor="business-name">Business name</Label>
            <Input
              id="business-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="currency">Currency</Label>
            <Input
              id="currency"
              value={currencyLocked ? initialCurrencyCode : currencyCode}
              onChange={(event) => setCurrencyCode(event.target.value.toUpperCase())}
              maxLength={3}
              readOnly={currencyLocked}
              disabled={currencyLocked}
            />
            {currencyLocked ? (
              <p className="text-xs text-muted-foreground">
                Currency is fixed after setup.
              </p>
            ) : null}
          </div>
          <Button type="submit" disabled={saving || !dirty}>
            {saving ? "Saving…" : "Save profile"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
