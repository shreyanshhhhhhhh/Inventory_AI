"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { errorMessage, type LoadResult } from "@/lib/load-result";

export type SettingsLocation = {
  id: string;
  name: string;
  address: string | null;
  isDefault: boolean;
  isActive: boolean;
};

export type SettingsTeamUser = {
  id: string;
  email: string;
  fullName: string;
  role: "owner" | "staff";
  isActive: boolean;
};

interface SettingsContextValue {
  isOwner: boolean;
  businessName: string;
  currencyCode: string;
  /** Currency is fixed once onboarding is complete (amounts are stored without conversion). */
  currencyLocked: boolean;
  /** Active and archived locations; filter on `isActive`. */
  locations: SettingsLocation[];
  teamUsers: SettingsTeamUser[];
  autoApproveBelow: string;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  saveBusinessProfile: (input: {
    name: string;
    currencyCode: string;
  }) => Promise<void>;
  createLocation: (input: {
    name: string;
    address?: string;
    isDefault?: boolean;
  }) => Promise<void>;
  updateLocation: (
    id: string,
    input: { name?: string; address?: string | null; isDefault?: boolean },
  ) => Promise<void>;
  archiveLocation: (id: string) => Promise<void>;
  restoreLocation: (id: string) => Promise<void>;
  createStaffUser: (input: {
    fullName: string;
    email: string;
    temporaryPassword: string;
  }) => Promise<void>;
  updateUserRole: (userId: string, role: "owner" | "staff") => Promise<void>;
  setUserActive: (userId: string, isActive: boolean) => Promise<void>;
  saveAutonomyRules: (autoApproveBelow: string | null) => Promise<void>;
}

type SettingsData = {
  locations: SettingsLocation[];
  teamUsers: SettingsTeamUser[];
  autoApproveBelow: string;
};

const EMPTY_SETTINGS: SettingsData = {
  locations: [],
  teamUsers: [],
  autoApproveBelow: "",
};

const SettingsContext = createContext<SettingsContextValue | null>(null);

async function fetchSettings(): Promise<LoadResult<SettingsData>> {
  try {
    const [locationRows, users, autonomy] = await Promise.all([
      api.settings.locations.list({ include_archived: true }),
      api.settings.users.list(),
      api.settings.autonomyRules.get(),
    ]);
    return {
      data: {
        locations: locationRows.map((row) => ({
          id: row.id,
          name: row.name,
          address: row.address,
          isDefault: row.is_default,
          isActive: row.is_active,
        })),
        teamUsers: users.map((row) => ({
          id: row.id,
          email: row.email,
          fullName: row.full_name,
          role: row.role,
          isActive: row.is_active,
        })),
        autoApproveBelow: autonomy.auto_approve_below_amount ?? "",
      },
      error: null,
    };
  } catch (err) {
    return { data: null, error: errorMessage(err, "Could not load settings.") };
  }
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const { business, isAuthenticated, isOwner, isOnboarded, refreshSession } = useAuth();
  const ready = isAuthenticated && isOwner;

  const [data, setData] = useState<SettingsData>(EMPTY_SETTINGS);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const apply = useCallback((result: LoadResult<SettingsData>) => {
    if (result.data) setData(result.data);
    setError(result.error);
    setIsLoading(false);
  }, []);

  const refresh = useCallback(async () => {
    if (!ready) return;
    apply(await fetchSettings());
  }, [ready, apply]);

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    void fetchSettings().then((result) => {
      if (!cancelled) apply(result);
    });
    return () => {
      cancelled = true;
    };
  }, [ready, apply]);

  const saveBusinessProfile = useCallback(
    async (input: { name: string; currencyCode: string }) => {
      await api.settings.business.update({
        name: input.name,
        ...(isOnboarded ? {} : { currency_code: input.currencyCode }),
      });
      await refreshSession();
    },
    [isOnboarded, refreshSession],
  );

  const createLocation = useCallback(
    async (input: { name: string; address?: string; isDefault?: boolean }) => {
      await api.settings.locations.create({
        name: input.name,
        address: input.address ?? null,
        is_default: input.isDefault ?? false,
      });
      await refresh();
    },
    [refresh],
  );

  const updateLocation = useCallback(
    async (
      id: string,
      input: { name?: string; address?: string | null; isDefault?: boolean },
    ) => {
      await api.settings.locations.update(id, {
        name: input.name,
        address: input.address,
        is_default: input.isDefault,
      });
      await refresh();
    },
    [refresh],
  );

  const archiveLocation = useCallback(
    async (id: string) => {
      await api.settings.locations.archive(id);
      await refresh();
    },
    [refresh],
  );

  const restoreLocation = useCallback(
    async (id: string) => {
      await api.settings.locations.restore(id);
      await refresh();
    },
    [refresh],
  );

  const createStaffUser = useCallback(
    async (input: {
      fullName: string;
      email: string;
      temporaryPassword: string;
    }) => {
      await api.settings.users.create({
        full_name: input.fullName,
        email: input.email,
        temporary_password: input.temporaryPassword,
      });
      await refresh();
    },
    [refresh],
  );

  const updateUserRole = useCallback(
    async (userId: string, role: "owner" | "staff") => {
      await api.settings.users.updateRole(userId, { role });
      if (role === "owner") {
        // Promoting someone else transfers ownership; the current user becomes staff.
        await refreshSession();
        return;
      }
      await refresh();
    },
    [refresh, refreshSession],
  );

  const setUserActive = useCallback(
    async (userId: string, isActive: boolean) => {
      await api.settings.users.setActive(userId, isActive);
      await refresh();
    },
    [refresh],
  );

  const saveAutonomyRules = useCallback(
    async (value: string | null) => {
      await api.settings.autonomyRules.update({
        auto_approve_below_amount: value,
      });
      await refresh();
    },
    [refresh],
  );

  const value = useMemo<SettingsContextValue>(() => {
    const current = ready ? data : EMPTY_SETTINGS;
    return {
      isOwner,
      businessName: business?.name ?? "",
      currencyCode: business?.currency_code ?? "USD",
      currencyLocked: isOnboarded,
      locations: current.locations,
      teamUsers: current.teamUsers,
      autoApproveBelow: current.autoApproveBelow,
      isLoading: ready && isLoading,
      error: ready ? error : null,
      refresh,
      saveBusinessProfile,
      createLocation,
      updateLocation,
      archiveLocation,
      restoreLocation,
      createStaffUser,
      updateUserRole,
      setUserActive,
      saveAutonomyRules,
    };
  }, [
    ready,
    data,
    isOwner,
    business?.name,
    business?.currency_code,
    isOnboarded,
    isLoading,
    error,
    refresh,
    saveBusinessProfile,
    createLocation,
    updateLocation,
    archiveLocation,
    restoreLocation,
    createStaffUser,
    updateUserRole,
    setUserActive,
    saveAutonomyRules,
  ]);

  return (
    <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>
  );
}

export function useSettings(): SettingsContextValue {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error("useSettings must be used within SettingsProvider");
  }
  return context;
}
