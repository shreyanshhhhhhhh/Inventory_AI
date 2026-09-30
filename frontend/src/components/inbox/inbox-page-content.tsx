"use client";

import { Bot, Inbox } from "lucide-react";

import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";
import { StatusBadge } from "@/components/common/status-badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export function InboxPageContent() {
  return (
    <>
      <PageHeader
        title="Agent Inbox"
        description="Review agent proposals before they become purchase orders or stock actions."
      />

      <Tabs defaultValue="approvals">
        <TabsList>
          <TabsTrigger value="approvals">Approvals</TabsTrigger>
          <TabsTrigger value="exceptions">Exceptions</TabsTrigger>
        </TabsList>

        <TabsContent value="approvals" className="mt-4 space-y-4">
          <EmptyState
            icon={Inbox}
            title="No approval requests"
            message="Agent Inbox is a Phase 3 feature. Nothing here calls a model in Phase 1."
          />

          <Card className="border-dashed">
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <CardTitle>Example of a future suggestion</CardTitle>
                  <CardDescription>
                    Static preview only — buttons are disabled.
                  </CardDescription>
                </div>
                <StatusBadge variant="severity-medium" label="72% confidence" />
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-sm font-medium">
                  Draft PO for baby spinach and avocados
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Spinach is below reorder at the front store and avocados are
                  out. Green Valley can deliver in 2 days.
                </p>
              </div>
              <ul className="space-y-2 text-sm">
                <li className="rounded-lg bg-muted/50 px-3 py-2">
                  Baby spinach on hand: 14 · reorder point: 24
                </li>
                <li className="rounded-lg bg-muted/50 px-3 py-2">
                  Avocados on hand: 0 · reorder point: 30
                </li>
                <li className="rounded-lg bg-muted/50 px-3 py-2">
                  Preferred supplier lead time: 2 days
                </li>
              </ul>
              <div className="flex flex-wrap gap-2">
                <Button disabled>Approve</Button>
                <Button variant="outline" disabled>
                  Reject
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="exceptions" className="mt-4">
          <EmptyState
            icon={Bot}
            title="No exceptions"
            message="Overdue purchase orders and receive mismatches will create exception cards in a later phase."
          />
        </TabsContent>
      </Tabs>
    </>
  );
}
