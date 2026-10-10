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

export type AutonomyRulesSaveInput = {
  autoApproveBelow: string | null;
  exceptionScanEnabled: boolean;
  exceptionScanHourUtc: number;
  chaseFollowupDays: number;
};

interface AutonomyRulesCardProps {
  initialAutoApproveBelow: string;
  initialExceptionScanEnabled: boolean;
  initialExceptionScanHourUtc: number;
  initialChaseFollowupDays: number;
  onSave: (input: AutonomyRulesSaveInput) => Promise<void>;
}

export function AutonomyRulesCard({
  initialAutoApproveBelow,
  initialExceptionScanEnabled,
  initialExceptionScanHourUtc,
  initialChaseFollowupDays,
  onSave,
}: AutonomyRulesCardProps) {
  const [autoApprove, setAutoApprove] = useState(initialAutoApproveBelow);
  const [scanEnabled, setScanEnabled] = useState(initialExceptionScanEnabled);
  const [scanHour, setScanHour] = useState(String(initialExceptionScanHourUtc));
  const [chaseDays, setChaseDays] = useState(String(initialChaseFollowupDays));
  const [saving, setSaving] = useState(false);

  const trimmed = autoApprove.trim();
  const hour = Number(scanHour);
  const chase = Number(chaseDays);

  const unchanged =
    trimmed === initialAutoApproveBelow.trim() &&
    scanEnabled === initialExceptionScanEnabled &&
    hour === initialExceptionScanHourUtc &&
    chase === initialChaseFollowupDays;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (trimmed !== "" && !/^\d+(\.\d+)?$/.test(trimmed)) {
      toast.error("Enter an amount like 250.00, or leave it empty.");
      return;
    }
    if (!Number.isInteger(hour) || hour < 0 || hour > 23) {
      toast.error("Scan hour must be an integer from 0 to 23 (UTC).");
      return;
    }
    if (!Number.isInteger(chase) || chase < 1) {
      toast.error("Chase follow-up days must be at least 1.");
      return;
    }
    setSaving(true);
    try {
      await onSave({
        autoApproveBelow: trimmed === "" ? null : trimmed,
        exceptionScanEnabled: scanEnabled,
        exceptionScanHourUtc: hour,
        chaseFollowupDays: chase,
      });
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
          Agent thresholds and the nightly exception scan schedule.
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
              value={autoApprove}
              onChange={(event) => setAutoApprove(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Purchase orders below this amount could be auto-approved by an agent later.
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="exception-scan">Nightly exception scan</Label>
            <label className="flex items-center gap-2 text-sm" htmlFor="exception-scan">
              <input
                id="exception-scan"
                type="checkbox"
                checked={scanEnabled}
                onChange={(event) => setScanEnabled(event.target.checked)}
              />
              Run the exception monitor on a schedule
            </label>
            <Label htmlFor="scan-hour">Scan hour (UTC)</Label>
            <Input
              id="scan-hour"
              inputMode="numeric"
              value={scanHour}
              onChange={(event) => setScanHour(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Owners can also POST /api/v1/jobs/exception-scan, or a cron job can call it with
              X-Job-Secret.
            </p>
            <Label htmlFor="chase-days">Chase follow-up days</Label>
            <Input
              id="chase-days"
              inputMode="numeric"
              value={chaseDays}
              onChange={(event) => setChaseDays(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              After a sent chase has no reply for this many days, the exception monitor raises a
              low-severity finding.
            </p>
          </div>
          <div className="flex items-start sm:col-span-2">
            <Button type="submit" disabled={saving || unchanged}>
              {saving ? "Saving…" : "Save rules"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
