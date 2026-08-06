import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { User } from "@/types";
import * as authApi from "@/api/auth";
import { setAccessToken, setRefreshToken, getRefreshToken, clearTokens, refreshAccessToken } from "@/api/client";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On first load, if a refresh token exists, silently try to restore the
  // session by fetching /auth/me (the request interceptor will trigger a
  // token refresh automatically on the 401 this produces, since there's no
  // access token in memory yet — see api/client.ts).
  useEffect(() => {
    async function restoreSession() {
      const refreshToken = getRefreshToken();
      if (!refreshToken) {
        setIsLoading(false);
        return;
      }
      try {
        const newAccessToken = await refreshAccessToken();
        if (!newAccessToken) {
          clearTokens();
          setIsLoading(false);
          return;
        }
        const me = await authApi.fetchMe();
        setUser(me);
      } catch {
        clearTokens();
      } finally {
        setIsLoading(false);
      }
    }
    restoreSession();

    function handleAuthExpired() {
      setUser(null);
    }
    window.addEventListener("knowsphere:auth-expired", handleAuthExpired);
    return () => window.removeEventListener("knowsphere:auth-expired", handleAuthExpired);
  }, []);

  async function login(email: string, password: string) {
    const data = await authApi.login(email, password);
    setAccessToken(data.access_token);
    setRefreshToken(data.refresh_token);
    setUser(data.user);
  }

  async function logout() {
    await authApi.logout();
    clearTokens();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, isAuthenticated: !!user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
