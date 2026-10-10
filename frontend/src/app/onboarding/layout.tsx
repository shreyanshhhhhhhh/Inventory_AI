import type { ReactNode } from "react";

import { ProtectedRoute } from "@/components/protected-route";

export default function OnboardingLayout({ children }: { children: ReactNode }) {
  return (
    <ProtectedRoute mode="onboarding">
      <div className="flex min-h-full flex-1 flex-col bg-muted/30">{children}</div>
    </ProtectedRoute>
  );
}
