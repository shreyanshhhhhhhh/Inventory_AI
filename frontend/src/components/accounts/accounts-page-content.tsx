"use client";

import { useState } from "react";

import { ProfileTab } from "@/components/accounts/profile-tab";
import { SpendSnapshotTab } from "@/components/accounts/spend-snapshot-tab";
import { TeamTab } from "@/components/accounts/team-tab";
import { PageHeader } from "@/components/common/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/lib/auth-context";

export function AccountsPageContent() {
  const { isOwner } = useAuth();
  const [tab, setTab] = useState("profile");
  // Ownership can be transferred away while the Team tab is open.
  const activeTab = !isOwner && tab === "team" ? "profile" : tab;

  return (
    <>
      <PageHeader
        title="Accounts"
        description={
          isOwner
            ? "Your profile, your team, and an operational spend snapshot."
            : "Your profile and an operational spend snapshot."
        }
      />

      <Tabs
        value={activeTab}
        onValueChange={(value) => {
          if (typeof value === "string") setTab(value);
        }}
      >
        <TabsList>
          <TabsTrigger value="profile">Profile</TabsTrigger>
          {isOwner ? <TabsTrigger value="team">Team</TabsTrigger> : null}
          <TabsTrigger value="spend">Spend snapshot</TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="mt-4">
          <ProfileTab />
        </TabsContent>
        {isOwner ? (
          <TabsContent value="team" className="mt-4">
            <TeamTab />
          </TabsContent>
        ) : null}
        <TabsContent value="spend" className="mt-4">
          <SpendSnapshotTab />
        </TabsContent>
      </Tabs>
    </>
  );
}
