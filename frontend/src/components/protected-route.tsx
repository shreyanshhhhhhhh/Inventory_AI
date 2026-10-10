"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-context";

type ProtectedRouteProps = {
  children: ReactNode;
  /** "app" pages need a finished onboarding; the "onboarding" page needs an unfinished one. */
  mode?: "app" | "onboarding";
};

export function ProtectedRoute({ children, mode = "app" }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, isOnboarded, isOwner, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }
    if (mode === "app" && !isOnboarded && isOwner) {
      router.replace("/onboarding");
    } else if (mode === "onboarding" && (isOnboarded || !isOwner)) {
      router.replace("/");
    }
  }, [isAuthenticated, isLoading, isOnboarded, isOwner, mode, pathname, router]);

  if (isLoading) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  if (mode === "app" && !isOnboarded) {
    if (isOwner) return null;
    return (
      <div className="mx-auto flex min-h-svh max-w-md flex-col items-center justify-center gap-4 p-8 text-center">
        <h1 className="text-xl font-semibold">Setup in progress</h1>
        <p className="text-sm text-muted-foreground">
          The business owner has not finished setting up this workspace yet. Check back once
          onboarding is complete.
        </p>
        <Button variant="outline" onClick={() => void logout()}>
          Sign out
        </Button>
      </div>
    );
  }

  if (mode === "onboarding" && (isOnboarded || !isOwner)) {
    return null;
  }

  return children;
}
