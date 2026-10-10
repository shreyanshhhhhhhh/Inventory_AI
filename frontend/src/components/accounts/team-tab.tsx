"use client";

import { UserPlus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { DataTable, type DataTableColumn } from "@/components/common/data-table";
import { FormDialog } from "@/components/common/form-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { showApiErrorToast } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useSettings, type SettingsTeamUser } from "@/lib/settings-hooks";

const MIN_PASSWORD_LENGTH = 8;

type PendingAction =
  | { kind: "make-owner"; user: SettingsTeamUser }
  | { kind: "deactivate"; user: SettingsTeamUser }
  | { kind: "reactivate"; user: SettingsTeamUser };

export function TeamTab() {
  const { user: currentUser } = useAuth();
  const {
    teamUsers,
    isLoading,
    error,
    refresh,
    createStaffUser,
    updateUserRole,
    setUserActive,
  } = useSettings();

  const [addOpen, setAddOpen] = useState(false);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [working, setWorking] = useState(false);

  const runPending = async () => {
    if (!pending) return;
    setWorking(true);
    try {
      if (pending.kind === "make-owner") {
        await updateUserRole(pending.user.id, "owner");
        toast.success(`${pending.user.fullName} is now the owner`);
      } else {
        const activate = pending.kind === "reactivate";
        await setUserActive(pending.user.id, activate);
        toast.success(
          activate
            ? `${pending.user.fullName} reactivated`
            : `${pending.user.fullName} deactivated`,
        );
      }
      setPending(null);
    } catch (err) {
      showApiErrorToast(err);
    } finally {
      setWorking(false);
    }
  };

  const columns: DataTableColumn<SettingsTeamUser>[] = [
    {
      id: "name",
      header: "Name",
      cell: (row) => (
        <span className="font-medium">
          {row.fullName}
          {row.id === currentUser?.id ? (
            <span className="ml-1 font-normal text-muted-foreground">(you)</span>
          ) : null}
        </span>
      ),
    },
    { id: "email", header: "Email", cell: (row) => row.email },
    {
      id: "role",
      header: "Role",
      cell: (row) => (
        <Badge variant={row.role === "owner" ? "default" : "secondary"}>
          {row.role === "owner" ? "Owner" : "Staff"}
        </Badge>
      ),
    },
    {
      id: "status",
      header: "Status",
      cell: (row) =>
        row.isActive ? (
          <Badge variant="outline">Active</Badge>
        ) : (
          <Badge variant="destructive">Deactivated</Badge>
        ),
    },
    {
      id: "actions",
      header: "",
      className: "text-right",
      cell: (row) => {
        if (row.id === currentUser?.id || row.role === "owner") return null;
        return (
          <div className="flex justify-end gap-2">
            {row.isActive ? (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPending({ kind: "make-owner", user: row })}
                >
                  Make owner
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setPending({ kind: "deactivate", user: row })}
                >
                  Deactivate
                </Button>
              </>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPending({ kind: "reactivate", user: row })}
              >
                Reactivate
              </Button>
            )}
          </div>
        );
      },
    },
  ];

  if (isLoading) {
    return <Skeleton className="h-64 w-full" />;
  }

  return (
    <div className="space-y-4">
      {error ? (
        <div className="flex items-center justify-between gap-2 rounded-lg border border-destructive/40 p-3">
          <p className="text-sm text-destructive">{error}</p>
          <Button variant="outline" size="sm" onClick={() => void refresh()}>
            Retry
          </Button>
        </div>
      ) : null}

      <DataTable
        data={teamUsers}
        columns={columns}
        getRowId={(row) => row.id}
        searchPlaceholder="Search team…"
        pageSize={10}
        toolbar={
          <Button onClick={() => setAddOpen(true)}>
            <UserPlus />
            Add staff user
          </Button>
        }
        emptyState={
          <p className="py-8 text-center text-sm text-muted-foreground">
            No team members yet.
          </p>
        }
      />

      <p className="text-xs text-muted-foreground">
        Deactivated users cannot sign in and their sessions are revoked. Their stock
        movements and audit history are kept.
      </p>

      {addOpen ? (
        <AddStaffDialog
          onClose={() => setAddOpen(false)}
          onCreate={createStaffUser}
        />
      ) : null}

      {pending ? (
        <FormDialog
          open
          onOpenChange={(open) => {
            if (!open && !working) setPending(null);
          }}
          title={confirmTitle(pending)}
          description={confirmDescription(pending)}
          submitLabel={working ? "Working…" : confirmLabel(pending)}
          isSubmitting={working}
          onSubmit={() => void runPending()}
        >
          {null}
        </FormDialog>
      ) : null}
    </div>
  );
}

function confirmTitle(action: PendingAction): string {
  switch (action.kind) {
    case "make-owner":
      return `Transfer ownership to ${action.user.fullName}?`;
    case "deactivate":
      return `Deactivate ${action.user.fullName}?`;
    case "reactivate":
      return `Reactivate ${action.user.fullName}?`;
  }
}

function confirmDescription(action: PendingAction): string {
  switch (action.kind) {
    case "make-owner":
      return "There is one owner per business. You will become staff and lose access to settings and team management. Only the new owner can transfer it back.";
    case "deactivate":
      return "They will be signed out everywhere and cannot sign in until reactivated. Their history is kept.";
    case "reactivate":
      return "They will be able to sign in again with their existing password.";
  }
}

function confirmLabel(action: PendingAction): string {
  switch (action.kind) {
    case "make-owner":
      return "Transfer ownership";
    case "deactivate":
      return "Deactivate";
    case "reactivate":
      return "Reactivate";
  }
}

function AddStaffDialog({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (input: {
    fullName: string;
    email: string;
    temporaryPassword: string;
  }) => Promise<void>;
}) {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async () => {
    if (!fullName.trim() || !email.trim()) {
      toast.error("Name and email are required.");
      return;
    }
    if (password.length < MIN_PASSWORD_LENGTH) {
      toast.error(
        `Temporary password must be at least ${MIN_PASSWORD_LENGTH} characters.`,
      );
      return;
    }
    setSaving(true);
    try {
      await onCreate({
        fullName: fullName.trim(),
        email: email.trim(),
        temporaryPassword: password,
      });
      toast.success("Staff user created. Share the temporary password with them.");
      onClose();
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
      title="Add staff user"
      description="No invite email is sent. Share the temporary password with them directly."
      submitLabel={saving ? "Creating…" : "Create staff user"}
      isSubmitting={saving}
      onSubmit={() => void handleSubmit()}
    >
      <div className="space-y-2">
        <Label htmlFor="staff-full-name">Full name</Label>
        <Input
          id="staff-full-name"
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="staff-email">Email</Label>
        <Input
          id="staff-email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="staff-password">Temporary password</Label>
        <Input
          id="staff-password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <p className="text-xs text-muted-foreground">
          At least {MIN_PASSWORD_LENGTH} characters.
        </p>
      </div>
    </FormDialog>
  );
}
