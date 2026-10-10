import { PageContainer } from "@/components/common/page-container";
import { InboxPageContent } from "@/components/inbox/inbox-page-content";
import { Suspense } from "react";

export default function InboxPage() {
  return (
    <PageContainer>
      <Suspense>
        <InboxPageContent />
      </Suspense>
    </PageContainer>
  );
}
