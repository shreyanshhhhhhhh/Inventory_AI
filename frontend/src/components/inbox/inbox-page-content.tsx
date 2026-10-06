"use client";

import { Bot } from "lucide-react";

import { ApprovalsTab } from "@/components/inbox/approvals-tab";
import { ChatPanel } from "@/components/inbox/chat-panel";
import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useInboxSuggestions } from "@/lib/chat/suggestions";

export function InboxPageContent() {
  const { pendingCount } = useInboxSuggestions();
  return (
    <>
      <PageHeader
        title="Agent Inbox"
        description="Chat with the orchestrator, then approve drafts before they become purchase orders or email."
      />

      <Tabs defaultValue="chat">
        <TabsList>
          <TabsTrigger value="chat">Chat</TabsTrigger>
          <TabsTrigger value="approvals">
            Approvals{pendingCount > 0 ? ` (${pendingCount})` : ""}
          </TabsTrigger>
          <TabsTrigger value="exceptions">Exceptions</TabsTrigger>
        </TabsList>

        <TabsContent value="chat" className="mt-4" keepMounted>
          <ChatPanel />
        </TabsContent>
        <TabsContent value="approvals" className="mt-4">
          <ApprovalsTab />
        </TabsContent>
        <TabsContent value="exceptions" className="mt-4">
          <EmptyState
            icon={Bot}
            title="No exceptions"
            message="Exception cards from /scan appear in chat. Nightly scans are owner-configurable in Settings."
          />
        </TabsContent>
      </Tabs>
    </>
  );
}
