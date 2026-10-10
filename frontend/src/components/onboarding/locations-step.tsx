"use client";

import { MapPin, Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { StepFooter, type StepNavigation } from "@/components/onboarding/step-footer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { showApiErrorToast } from "@/lib/api";
import { useSettings } from "@/lib/settings-hooks";

interface LocationsStepProps extends StepNavigation {
  onChanged: () => Promise<void>;
}

export function LocationsStep({ onNext, onBack, onChanged }: LocationsStepProps) {
  const { locations, isLoading, error, createLocation, updateLocation, archiveLocation } =
    useSettings();
  const activeLocations = locations.filter((location) => location.isActive);

  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [makeDefault, setMakeDefault] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const handleAdd = async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      toast.error("Location name is required.");
      return;
    }
    setSubmitting(true);
    try {
      await createLocation({
        name: trimmed,
        address: address.trim() || undefined,
        isDefault: makeDefault || activeLocations.length === 0,
      });
      await onChanged();
      toast.success("Location added");
      setName("");
      setAddress("");
      setMakeDefault(false);
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setSubmitting(false);
    }
  };

  const runRowAction = async (id: string, action: () => Promise<void>, message: string) => {
    setBusyId(id);
    try {
      await action();
      await onChanged();
      toast.success(message);
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-6">
      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : activeLocations.length === 0 ? (
        <p className="rounded-md border border-dashed p-4 text-center text-sm text-muted-foreground">
          No locations yet. Add the shop, warehouse, or storeroom where you keep stock.
        </p>
      ) : (
        <ul className="divide-y rounded-md border">
          {activeLocations.map((location) => (
            <li
              key={location.id}
              className="flex flex-wrap items-center justify-between gap-2 p-3"
            >
              <div className="flex min-w-0 items-start gap-2">
                <MapPin className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0">
                  <p className="flex items-center gap-2 font-medium">
                    {location.name}
                    {location.isDefault ? <Badge variant="secondary">Default</Badge> : null}
                  </p>
                  {location.address ? (
                    <p className="truncate text-xs text-muted-foreground">
                      {location.address}
                    </p>
                  ) : null}
                </div>
              </div>
              {location.isDefault ? null : (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busyId !== null}
                    onClick={() =>
                      void runRowAction(
                        location.id,
                        () => updateLocation(location.id, { isDefault: true }),
                        `${location.name} is now the default`,
                      )
                    }
                  >
                    Make default
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={busyId !== null}
                    onClick={() =>
                      void runRowAction(
                        location.id,
                        () => archiveLocation(location.id),
                        `${location.name} removed`,
                      )
                    }
                  >
                    Remove
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <form
        className="space-y-4 rounded-md border p-4"
        onSubmit={(event) => {
          event.preventDefault();
          void handleAdd();
        }}
      >
        <p className="text-sm font-medium">Add a location</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="onboarding-location-name">Name</Label>
            <Input
              id="onboarding-location-name"
              value={name}
              placeholder="Main store"
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="onboarding-location-address">Address (optional)</Label>
            <Input
              id="onboarding-location-address"
              value={address}
              onChange={(event) => setAddress(event.target.value)}
            />
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={makeDefault || activeLocations.length === 0}
              disabled={activeLocations.length === 0}
              onChange={(event) => setMakeDefault(event.target.checked)}
              className="size-4 rounded border"
            />
            Make this the default location
          </label>
          <Button type="submit" variant="secondary" disabled={submitting}>
            <Plus />
            {submitting ? "Adding…" : "Add location"}
          </Button>
        </div>
      </form>

      <StepFooter
        onBack={onBack}
        onNext={onNext}
        nextDisabled={isLoading || activeLocations.length === 0}
        hint={
          activeLocations.length === 0
            ? "Add at least one location to continue."
            : "One location is the default for new stock and purchase orders."
        }
      />
    </div>
  );
}
