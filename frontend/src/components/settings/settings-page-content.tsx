"use client";

import { ShieldAlert } from "lucide-react";

import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";
import { AutonomyRulesCard } from "@/components/settings/autonomy-rules-card";
import { BusinessProfileCard } from "@/components/settings/business-profile-card";
import { LocationsCard } from "@/components/settings/locations-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useSettings } from "@/lib/settings-hooks";

const DESCRIPTION = "Business profile, locations, and autonomy rules.";

export function SettingsPageContent() {
  const {
    isOwner,
    businessName,
    currencyCode,
    currencyLocked,
    locations,
    autoApproveBelow,
    isLoading,
    error,
    refresh,
    saveBusinessProfile,
    createLocation,
    updateLocation,
    archiveLocation,
    restoreLocation,
    saveAutonomyRules,
  } = useSettings();

  if (!isOwner) {
    return (
      <>
        <PageHeader title="Settings" description={DESCRIPTION} />
        <EmptyState
          icon={ShieldAlert}
          title="Owner access required"
          message="Only the owner can change settings."
        />
      </>
    );
  }

  if (isLoading) {
    return (
      <>
        <PageHeader title="Settings" description={DESCRIPTION} />
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-40 w-full lg:col-span-2" />
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader title="Settings" description={DESCRIPTION} />

      {error ? (
        <div className="flex items-center justify-between gap-2 rounded-lg border border-destructive/40 p-3">
          <p className="text-sm text-destructive">{error}</p>
          <Button variant="outline" size="sm" onClick={() => void refresh()}>
            Retry
          </Button>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <BusinessProfileCard
          key={`${businessName}:${currencyCode}:${String(currencyLocked)}`}
          initialName={businessName}
          initialCurrencyCode={currencyCode}
          currencyLocked={currencyLocked}
          onSave={saveBusinessProfile}
        />
        <LocationsCard
          locations={locations}
          onCreate={createLocation}
          onUpdate={updateLocation}
          onArchive={archiveLocation}
          onRestore={restoreLocation}
        />
        <AutonomyRulesCard
          key={autoApproveBelow}
          initialAutoApproveBelow={autoApproveBelow}
          onSave={saveAutonomyRules}
        />
      </div>
    </>
  );
}
