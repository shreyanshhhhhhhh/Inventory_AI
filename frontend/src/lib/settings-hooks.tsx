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

export type SettingsLocation = {
  id: string;
  name: string;
  address: string | null;
  isDefault: boolean;
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
  locations: SettingsLocation[];
  teamUsers: SettingsTeamUser[];
  autoApproveBelow: string;
  exceptionScanEnabled: boolean;
  exceptionScanHourUtc: number;
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
  createStaffUser: (input: {
    fullName: string;
    email: string;
    temporaryPassword: string;
  }) => Promise<void>;
  updateUserRole: (userId: string, role: "owner" | "staff") => Promise<void>;
  saveAutonomyRules: (input: {
    autoApproveBelow: string | null;
    exceptionScanEnabled: boolean;
    exceptionScanHourUtc: number;
  }) => Promise<void>;
}

const SettingsContext = createContext<SettingsContextValue | null>(null);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const { user, business, isAuthenticated, refreshSession } = useAuth();
  const isOwner = user?.role === "owner";

  const [businessName, setBusinessName] = useState("");
  const [currencyCode, setCurrencyCode] = useState("USD");
  const [locations, setLocations] = useState<SettingsLocation[]>([]);
  const [teamUsers, setTeamUsers] = useState<SettingsTeamUser[]>([]);
  const [autoApproveBelow, setAutoApproveBelow] = useState("");
  const [exceptionScanEnabled, setExceptionScanEnabled] = useState(true);
  const [exceptionScanHourUtc, setExceptionScanHourUtc] = useState(2);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!isAuthenticated || !isOwner) {
      setBusinessName(business?.name ?? "");
      setCurrencyCode(business?.currency_code ?? "USD");
      setLocations([]);
      setTeamUsers([]);
      setAutoApproveBelow("");
      setExceptionScanEnabled(true);
      setExceptionScanHourUtc(2);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const [currentBusiness, locationRows, users, autonomy] = await Promise.all([
        api.business.current(),
        api.settings.locations.list(),
        api.settings.users.list(),
        api.settings.autonomyRules.get(),
      ]);
      setBusinessName(currentBusiness.name);
      setCurrencyCode(currentBusiness.currency_code);
      setLocations(
        locationRows.map((row) => ({
          id: row.id,
          name: row.name,
          address: row.address,
          isDefault: row.is_default,
        })),
      );
      setTeamUsers(
        users.map((row) => ({
          id: row.id,
          email: row.email,
          fullName: row.full_name,
          role: row.role as "owner" | "staff",
          isActive: row.is_active,
        })),
      );
      setAutoApproveBelow(autonomy.auto_approve_below_amount ?? "");
      setExceptionScanEnabled(autonomy.exception_scan_enabled);
      setExceptionScanHourUtc(autonomy.exception_scan_hour_utc);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load settings.");
    } finally {
      setIsLoading(false);
    }
  }, [business?.currency_code, business?.name, isAuthenticated, isOwner]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const saveBusinessProfile = useCallback(
    async (input: { name: string; currencyCode: string }) => {
      await api.settings.business.update({
        name: input.name,
        currency_code: input.currencyCode,
      });
      await refreshSession();
      await refresh();
    },
    [refresh, refreshSession],
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
      await refresh();
    },
    [refresh],
  );

  const saveAutonomyRules = useCallback(
    async (input: {
      autoApproveBelow: string | null;
      exceptionScanEnabled: boolean;
      exceptionScanHourUtc: number;
    }) => {
      await api.settings.autonomyRules.update({
        auto_approve_below_amount: input.autoApproveBelow,
        exception_scan_enabled: input.exceptionScanEnabled,
        exception_scan_hour_utc: input.exceptionScanHourUtc,
      });
      await refresh();
    },
    [refresh],
  );

  const value = useMemo<SettingsContextValue>(
    () => ({
      isOwner,
      businessName,
      currencyCode,
      locations,
      teamUsers,
      autoApproveBelow,
      exceptionScanEnabled,
      exceptionScanHourUtc,
      isLoading,
      error,
      refresh,
      saveBusinessProfile,
      createLocation,
      updateLocation,
      archiveLocation,
      createStaffUser,
      updateUserRole,
      saveAutonomyRules,
    }),
    [
      isOwner,
      businessName,
      currencyCode,
      locations,
      teamUsers,
      autoApproveBelow,
      exceptionScanEnabled,
      exceptionScanHourUtc,
      isLoading,
      error,
      refresh,
      saveBusinessProfile,
      createLocation,
      updateLocation,
      archiveLocation,
      createStaffUser,
      updateUserRole,
      saveAutonomyRules,
    ],
  );

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
