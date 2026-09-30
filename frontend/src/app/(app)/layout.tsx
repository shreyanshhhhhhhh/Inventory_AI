import { AppShell } from "@/components/app-shell";
import { ProtectedRoute } from "@/components/protected-route";

export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <ProtectedRoute>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  );
}
