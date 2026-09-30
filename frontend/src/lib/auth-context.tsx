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
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from "@/lib/auth-storage";

export type AuthUser = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  business_id: string;
};

export type AuthBusiness = {
  id: string;
  name: string;
  currency_code: string;
};

interface AuthContextValue {
  user: AuthUser | null;
  business: AuthBusiness | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (input: {
    full_name: string;
    email: string;
    password: string;
    business_name: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function loadSession(): Promise<{
  user: AuthUser;
  business: AuthBusiness;
}> {
  const me = await api.auth.me();
  const business = await api.business.current();
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

  const persistTokens = useCallback(
    async (accessToken: string, refreshToken: string) => {
      setTokens(accessToken, refreshToken);
      await refreshSession();
    },
    [refreshSession],
  );

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await api.auth.login({ email, password });
      await persistTokens(tokens.access_token, tokens.refresh_token);
      router.replace("/");
    },
    [persistTokens, router],
  );

  const signup = useCallback(
    async (input: {
      full_name: string;
      email: string;
      password: string;
      business_name: string;
    }) => {
      const tokens = await api.auth.signup(input);
      await persistTokens(tokens.access_token, tokens.refresh_token);
      router.replace("/");
    },
    [persistTokens, router],
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
      login,
      signup,
      logout,
      refreshSession,
    }),
    [user, business, isLoading, login, signup, logout, refreshSession],
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
