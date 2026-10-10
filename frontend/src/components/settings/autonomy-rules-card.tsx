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

interface AutonomyRulesCardProps {
  initialAutoApproveBelow: string;
  onSave: (autoApproveBelow: string | null) => Promise<void>;
}

export function AutonomyRulesCard({
  initialAutoApproveBelow,
  onSave,
}: AutonomyRulesCardProps) {
  const [value, setValue] = useState(initialAutoApproveBelow);
  const [saving, setSaving] = useState(false);

  const trimmed = value.trim();

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (trimmed !== "" && !/^\d+(\.\d+)?$/.test(trimmed)) {
      toast.error("Enter an amount like 250.00, or leave it empty.");
      return;
    }
    setSaving(true);
    try {
      await onSave(trimmed === "" ? null : trimmed);
      toast.success("Autonomy rules saved");
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <CardTitle>Autonomy rules</CardTitle>
        <CardDescription>
          Stored for a future agent phase. Takes effect when agents launch.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={(event) => void handleSubmit(event)}
        >
          <div className="space-y-2">
            <Label htmlFor="auto-approve">Auto-approve below</Label>
            <Input
              id="auto-approve"
              inputMode="decimal"
              placeholder="e.g. 250.00"
              value={value}
              onChange={(event) => setValue(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Purchase orders below this amount could be auto-approved by an agent later.
            </p>
          </div>
          <div className="flex items-start sm:pt-6">
            <Button
              type="submit"
              disabled={saving || trimmed === initialAutoApproveBelow}
            >
              {saving ? "Saving…" : "Save rules"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
