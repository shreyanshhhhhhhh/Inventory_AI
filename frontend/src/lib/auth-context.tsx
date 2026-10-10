"use client";

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, ApiError } from "@/lib/api";
import type { ApiBusiness, ApiUser } from "@/lib/api-types";
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  onSessionExpired,
  setTokens,
} from "@/lib/auth-storage";
import { setDisplayCurrency } from "@/lib/format";

export type AuthUser = ApiUser;

export type AuthBusiness = ApiBusiness;

interface AuthContextValue {
  user: AuthUser | null;
  business: AuthBusiness | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isOwner: boolean;
  isOnboarded: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (input: {
    full_name: string;
    email: string;
    password: string;
    business_name: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
  /** Store a new token pair (e.g. after a password change) and reload the session. */
  applyTokens: (accessToken: string, refreshToken: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function loadSession(): Promise<{
  user: AuthUser;
  business: AuthBusiness;
}> {
  const [me, business] = await Promise.all([api.auth.me(), api.business.current()]);
  return { user: me, business };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [business, setBusiness] = useState<AuthBusiness | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshSession = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null);
      setBusiness(null);
      return;
    }
    const session = await loadSession();
    setDisplayCurrency(session.business.currency_code);
    setUser(session.user);
    setBusiness(session.business);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const bootstrap = async () => {
      try {
        if (getAccessToken()) {
          await refreshSession();
        }
      } catch {
        clearTokens();
        if (!cancelled) {
          setUser(null);
          setBusiness(null);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [refreshSession]);

  useEffect(
    () =>
      onSessionExpired(() => {
        setUser(null);
        setBusiness(null);
        router.replace("/login");
      }),
    [router],
  );

  const applyTokens = useCallback(
    async (accessToken: string, refreshToken: string) => {
      setTokens(accessToken, refreshToken);
      await refreshSession();
    },
    [refreshSession],
  );

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await api.auth.login({ email, password });
      await applyTokens(tokens.access_token, tokens.refresh_token);
      router.replace("/");
    },
    [applyTokens, router],
  );

  const signup = useCallback(
    async (input: {
      full_name: string;
      email: string;
      password: string;
      business_name: string;
    }) => {
      const tokens = await api.auth.signup(input);
      await applyTokens(tokens.access_token, tokens.refresh_token);
      router.replace("/onboarding");
    },
    [applyTokens, router],
  );

  const logout = useCallback(async () => {
    const refreshToken = getRefreshToken();
    try {
      if (refreshToken) {
        await api.auth.logout(refreshToken);
      }
    } catch {
      // still clear local session
    } finally {
      clearTokens();
      setUser(null);
      setBusiness(null);
      router.replace("/login");
    }
  }, [router]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      business,
      isLoading,
      isAuthenticated: user !== null,
      isOwner: user?.role === "owner",
      isOnboarded: business?.onboarding_completed ?? false,
      login,
      signup,
      logout,
      refreshSession,
      applyTokens,
    }),
    [user, business, isLoading, login, signup, logout, refreshSession, applyTokens],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

export function useAuthErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong.";
}
