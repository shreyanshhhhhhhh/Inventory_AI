"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { showApiErrorToast } from "@/lib/api";
import { useSettings } from "@/lib/settings-hooks";
import { ShieldAlert } from "lucide-react";

export function SettingsPageContent() {
  const {
    isOwner,
    businessName,
    currencyCode,
    locations,
    teamUsers,
    autoApproveBelow,
    isLoading,
    error,
    saveBusinessProfile,
    createLocation,
    updateLocation,
    archiveLocation,
    createStaffUser,
    updateUserRole,
    saveAutonomyRules,
  } = useSettings();

  const [nameInput, setNameInput] = useState(businessName);
  const [currencyInput, setCurrencyInput] = useState(currencyCode);
  const [locationDrafts, setLocationDrafts] = useState<
    Record<string, { name: string; address: string }>
  >({});
  const [newLocationName, setNewLocationName] = useState("");
  const [staffName, setStaffName] = useState("");
  const [staffEmail, setStaffEmail] = useState("");
  const [staffPassword, setStaffPassword] = useState("");
  const [autoApproveInput, setAutoApproveInput] = useState(autoApproveBelow);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setNameInput(businessName);
    setCurrencyInput(currencyCode);
    setAutoApproveInput(autoApproveBelow);
    setLocationDrafts(
      Object.fromEntries(
        locations.map((location) => [
          location.id,
          { name: location.name, address: location.address ?? "" },
        ]),
      ),
    );
  }, [businessName, currencyCode, autoApproveBelow, locations]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveBusinessProfile({
        name: nameInput.trim(),
        currencyCode: currencyInput.trim().toUpperCase(),
      });
      await Promise.all(
        locations.map((location) => {
          const draft = locationDrafts[location.id];
          if (!draft) return Promise.resolve();
          return updateLocation(location.id, {
            name: draft.name.trim(),
            address: draft.address.trim() || null,
          });
        }),
      );
      await saveAutonomyRules(
        autoApproveInput.trim() === "" ? null : autoApproveInput.trim(),
      );
      toast.success("Settings saved");
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setSaving(false);
    }
  };

  const handleAddLocation = async () => {
    if (!newLocationName.trim()) {
      toast.error("Location name is required.");
      return;
    }
    try {
      await createLocation({ name: newLocationName.trim() });
      setNewLocationName("");
      toast.success("Location added");
    } catch (err) {
      showApiErrorToast(err);
    }
  };

  const handleAddStaff = async () => {
    if (!staffName.trim() || !staffEmail.trim() || staffPassword.length < 8) {
      toast.error("Name, email, and an 8+ character temporary password are required.");
      return;
    }
    try {
      await createStaffUser({
        fullName: staffName.trim(),
        email: staffEmail.trim(),
        temporaryPassword: staffPassword,
      });
      setStaffName("");
      setStaffEmail("");
      setStaffPassword("");
      toast.success("Staff user created");
    } catch (err) {
      showApiErrorToast(err);
    }
  };

  if (isLoading) {
    return (
      <>
        <PageHeader title="Settings" description="Business profile, team access, and autonomy rules." />
        <Skeleton className="h-80 w-full" />
      </>
    );
  }

  if (!isOwner) {
    return (
      <>
        <PageHeader
          title="Settings"
          description="Business profile, team access, and autonomy rules."
        />
        <EmptyState
          icon={ShieldAlert}
          title="Owner access required"
          message="Staff users can work with catalog, inventory, and orders. Settings and team management are limited to owners."
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Settings"
        description="Business profile, team access, and autonomy rules."
        action={
          <Button onClick={() => void handleSave()} disabled={saving}>
            {saving ? "Saving…" : "Save changes"}
          </Button>
        }
      />

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Business profile</CardTitle>
            <CardDescription>Name and currency for this business.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="business-name">Business name</Label>
              <Input
                id="business-name"
                value={nameInput}
                onChange={(event) => setNameInput(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="currency">Currency</Label>
              <Input
                id="currency"
                value={currencyInput}
                onChange={(event) => setCurrencyInput(event.target.value.toUpperCase())}
                maxLength={3}
              />
            </div>
            <div className="space-y-3">
              <Label>Locations</Label>
              {locations.map((location) => (
                <div key={location.id} className="space-y-2 rounded-lg border p-3">
                  <Input
                    value={locationDrafts[location.id]?.name ?? location.name}
                    onChange={(event) =>
                      setLocationDrafts({
                        ...locationDrafts,
                        [location.id]: {
                          name: event.target.value,
                          address: locationDrafts[location.id]?.address ?? "",
                        },
                      })
                    }
                  />
                  <Input
                    placeholder="Address (optional)"
                    value={locationDrafts[location.id]?.address ?? ""}
                    onChange={(event) =>
                      setLocationDrafts({
                        ...locationDrafts,
                        [location.id]: {
                          name: locationDrafts[location.id]?.name ?? location.name,
                          address: event.target.value,
                        },
                      })
                    }
                  />
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs text-muted-foreground">
                      {location.isDefault ? "Default location" : "Secondary location"}
                    </p>
                    {!location.isDefault && locations.length > 1 ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => void archiveLocation(location.id)}
                      >
                        Archive
                      </Button>
                    ) : null}
                  </div>
                </div>
              ))}
              <div className="flex gap-2">
                <Input
                  placeholder="New location name"
                  value={newLocationName}
                  onChange={(event) => setNewLocationName(event.target.value)}
                />
                <Button variant="outline" onClick={() => void handleAddLocation()}>
                  Add
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Users and roles</CardTitle>
            <CardDescription>Invite staff with a temporary password.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {teamUsers.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell>{user.fullName}</TableCell>
                    <TableCell>{user.email}</TableCell>
                    <TableCell>
                      {user.role === "owner" ? (
                        <span className="capitalize">{user.role}</span>
                      ) : (
                        <Select
                          value={user.role}
                          onValueChange={(value) => {
                            const role = value as "owner" | "staff" | null;
                            if (role !== "owner" && role !== "staff") return;
                            void updateUserRole(user.id, role).catch(showApiErrorToast);
                          }}
                        >
                          <SelectTrigger className="w-28">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="staff">Staff</SelectItem>
                            <SelectItem value="owner">Owner</SelectItem>
                          </SelectContent>
                        </Select>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            <div className="space-y-2 rounded-lg border p-3">
              <Label>Add staff user</Label>
              <Input
                placeholder="Full name"
                value={staffName}
                onChange={(event) => setStaffName(event.target.value)}
              />
              <Input
                placeholder="Email"
                type="email"
                value={staffEmail}
                onChange={(event) => setStaffEmail(event.target.value)}
              />
              <Input
                placeholder="Temporary password (8+ characters)"
                type="password"
                value={staffPassword}
                onChange={(event) => setStaffPassword(event.target.value)}
              />
              <Button variant="outline" onClick={() => void handleAddStaff()}>
                Create staff user
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Autonomy rules</CardTitle>
            <CardDescription>
              Stored for a future agent phase. Takes effect when agents launch.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="auto-approve">Auto-approve below</Label>
              <Input
                id="auto-approve"
                inputMode="decimal"
                placeholder="e.g. 250.00"
                value={autoApproveInput}
                onChange={(event) => setAutoApproveInput(event.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Purchase orders below this amount could be auto-approved by an agent later.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
