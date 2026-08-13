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
import { useRouter } from "next/navigation";
import { apiClient, ApiError, setAccessToken, setRefreshHandler } from "@/lib/api-client";

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  created_at: string;
}

export interface AuthOrganization {
  id: string;
  name: string;
  slug: string;
}

interface SignupResponse {
  user: AuthUser;
  organization: AuthOrganization;
  access_token: string;
}

interface LoginResponse {
  user: AuthUser;
  access_token: string;
}

interface RefreshResponse {
  access_token: string;
}

interface MeResponse {
  user: AuthUser;
  organization: AuthOrganization;
  role: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  organization: AuthOrganization | null;
  /** True until the initial silent-refresh attempt (on page load) resolves. */
  isLoading: boolean;
  isAuthenticated: boolean;
  signup: (email: string, password: string, name: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  /** Re-fetches GET /auth/me and resyncs local user/organization state —
   * used by Settings pages after a profile mutation instead of a full
   * page reload. */
  refreshMe: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Session state lives in memory only (React state), never localStorage —
 * plan.md's Security Architecture: "Access tokens are never persisted
 * client-side beyond memory/short-lived storage." Page reloads recover the
 * session via a silent POST /auth/refresh against the httpOnly refresh
 * cookie (handled automatically below and by api-client's 401→refresh
 * retry for every other request).
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [organization, setOrganization] = useState<AuthOrganization | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(async (): Promise<string | null> => {
    try {
      const data = await apiClient.postSkipAuthRetry<RefreshResponse>("/auth/refresh");
      setAccessToken(data.access_token);
      return data.access_token;
    } catch {
      setAccessToken(null);
      setUser(null);
      setOrganization(null);
      return null;
    }
  }, []);

  useEffect(() => {
    setRefreshHandler(refresh);

    (async () => {
      const token = await refresh();
      if (token) {
        try {
          const me = await apiClient.get<MeResponse>("/auth/me");
          setUser(me.user);
          setOrganization(me.organization);
        } catch {
          setAccessToken(null);
        }
      }
      setIsLoading(false);
    })();

    return () => setRefreshHandler(null);
  }, [refresh]);

  const signup = useCallback(async (email: string, password: string, name: string) => {
    const data = await apiClient.post<SignupResponse>("/auth/signup", { email, password, name });
    setAccessToken(data.access_token);
    setUser(data.user);
    setOrganization(data.organization);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = await apiClient.post<LoginResponse>("/auth/login", { email, password });
    setAccessToken(data.access_token);
    setUser(data.user);
    const me = await apiClient.get<MeResponse>("/auth/me");
    setOrganization(me.organization);
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiClient.post("/auth/logout");
    } finally {
      setAccessToken(null);
      setUser(null);
      setOrganization(null);
    }
  }, []);

  const refreshMe = useCallback(async () => {
    const me = await apiClient.get<MeResponse>("/auth/me");
    setUser(me.user);
    setOrganization(me.organization);
  }, []);

  const value = useMemo(
    () => ({
      user,
      organization,
      isLoading,
      isAuthenticated: user !== null,
      signup,
      login,
      logout,
      refreshMe,
    }),
    [user, organization, isLoading, signup, login, logout, refreshMe],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}

export { ApiError };

/** FR-007: guards a page/layout, redirecting unauthenticated users to
 * /login. Call from a client component; renders nothing meaningful while
 * the initial session check is in flight (the caller decides the loading UI). */
export function useRequireAuth(): AuthContextValue {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!auth.isLoading && !auth.isAuthenticated) {
      router.replace("/login");
    }
  }, [auth.isLoading, auth.isAuthenticated, router]);

  return auth;
}
