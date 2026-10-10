"use client";

import { ChevronDown, ChevronRight, MapPin, Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { FormDialog } from "@/components/common/form-dialog";
import { Badge } from "@/components/ui/badge";
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
import type { SettingsLocation } from "@/lib/settings-hooks";

type LocationInput = { name: string; address: string | null };

interface LocationsCardProps {
  locations: SettingsLocation[];
  onCreate: (input: { name: string; address?: string }) => Promise<void>;
  onUpdate: (
    id: string,
    input: { name?: string; address?: string | null; isDefault?: boolean },
  ) => Promise<void>;
  onArchive: (id: string) => Promise<void>;
  onRestore: (id: string) => Promise<void>;
}

type DialogState =
  | { mode: "create" }
  | { mode: "edit"; location: SettingsLocation }
  | null;

export function LocationsCard({
  locations,
  onCreate,
  onUpdate,
  onArchive,
  onRestore,
}: LocationsCardProps) {
  const [dialog, setDialog] = useState<DialogState>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const active = locations.filter((location) => location.isActive);
  const archived = locations.filter((location) => !location.isActive);

  const runRowAction = async (
    id: string,
    action: () => Promise<void>,
    successMessage: string,
  ) => {
    setBusyId(id);
    try {
      await action();
      toast.success(successMessage);
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setBusyId(null);
    }
  };

  const handleDialogSave = async (input: LocationInput) => {
    if (dialog?.mode === "edit") {
      await onUpdate(dialog.location.id, input);
      toast.success("Location updated");
    } else {
      await onCreate({ name: input.name, address: input.address ?? undefined });
      toast.success("Location added");
    }
    setDialog(null);
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-1.5">
            <CardTitle>Locations</CardTitle>
            <CardDescription>
              Where stock is kept. Archived locations keep their history.
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={() => setDialog({ mode: "create" })}>
            <Plus />
            Add
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {active.length === 0 ? (
          <p className="text-sm text-muted-foreground">No active locations.</p>
        ) : null}
        {active.map((location) => (
          <div
            key={location.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3"
          >
            <div className="min-w-0 space-y-0.5">
              <div className="flex items-center gap-2">
                <MapPin className="size-4 text-muted-foreground" />
                <span className="truncate font-medium">{location.name}</span>
                {location.isDefault ? <Badge variant="secondary">Default</Badge> : null}
              </div>
              {location.address ? (
                <p className="truncate pl-6 text-xs text-muted-foreground">
                  {location.address}
                </p>
              ) : null}
            </div>
            <div className="flex gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setDialog({ mode: "edit", location })}
              >
                Edit
              </Button>
              {!location.isDefault ? (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busyId === location.id}
                    onClick={() =>
                      void runRowAction(
                        location.id,
                        () => onUpdate(location.id, { isDefault: true }),
                        `${location.name} is now the default location`,
                      )
                    }
                  >
                    Set default
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busyId === location.id}
                    onClick={() =>
                      void runRowAction(
                        location.id,
                        () => onArchive(location.id),
                        `${location.name} archived`,
                      )
                    }
                  >
                    Archive
                  </Button>
                </>
              ) : null}
            </div>
          </div>
        ))}

        {archived.length > 0 ? (
          <div className="space-y-2 pt-1">
            <Button
              variant="ghost"
              size="sm"
              aria-expanded={showArchived}
              onClick={() => setShowArchived((open) => !open)}
            >
              {showArchived ? <ChevronDown /> : <ChevronRight />}
              {showArchived ? "Hide archived" : "Show archived"} ({archived.length})
            </Button>
            {showArchived
              ? archived.map((location) => (
                  <div
                    key={location.id}
                    className="flex items-center justify-between gap-2 rounded-lg border border-dashed p-3 text-muted-foreground"
                  >
                    <div className="min-w-0">
                      <span className="truncate">{location.name}</span>
                      {location.address ? (
                        <p className="truncate text-xs">{location.address}</p>
                      ) : null}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busyId === location.id}
                      onClick={() =>
                        void runRowAction(
                          location.id,
                          () => onRestore(location.id),
                          `${location.name} restored`,
                        )
                      }
                    >
                      Restore
                    </Button>
                  </div>
                ))
              : null}
          </div>
        ) : null}
      </CardContent>

      {dialog ? (
        <LocationDialog
          key={dialog.mode === "edit" ? dialog.location.id : "create"}
          title={dialog.mode === "edit" ? "Edit location" : "Add location"}
          initialName={dialog.mode === "edit" ? dialog.location.name : ""}
          initialAddress={dialog.mode === "edit" ? (dialog.location.address ?? "") : ""}
          onClose={() => setDialog(null)}
          onSave={handleDialogSave}
        />
      ) : null}
    </Card>
  );
}

function LocationDialog({
  title,
  initialName,
  initialAddress,
  onClose,
  onSave,
}: {
  title: string;
  initialName: string;
  initialAddress: string;
  onClose: () => void;
  onSave: (input: LocationInput) => Promise<void>;
}) {
  const [name, setName] = useState(initialName);
  const [address, setAddress] = useState(initialAddress);
  const [saving, setSaving] = useState(false);

  const handleSubmit = async () => {
    if (!name.trim()) {
      toast.error("Location name is required.");
      return;
    }
    setSaving(true);
    try {
      await onSave({ name: name.trim(), address: address.trim() || null });
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <FormDialog
      open
      onOpenChange={(open) => {
        if (!open && !saving) onClose();
      }}
      title={title}
      submitLabel={saving ? "Saving…" : "Save"}
      isSubmitting={saving}
      onSubmit={() => void handleSubmit()}
    >
      <div className="space-y-2">
        <Label htmlFor="location-name">Name</Label>
        <Input
          id="location-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="location-address">Address (optional)</Label>
        <Input
          id="location-address"
          value={address}
          onChange={(event) => setAddress(event.target.value)}
        />
      </div>
    </FormDialog>
  );
}
