import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import type { ApiResponse, LoginResponse } from "@/types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api/v1";

/**
 * Token storage strategy for Phase 1:
 * - Access token lives only in memory (this module) — never touches disk,
 *   minimizing XSS exposure.
 * - Refresh token is persisted in localStorage so a page reload doesn't log
 *   the user out. This is a reasonable Phase 1 tradeoff; a production
 *   hardening pass should move the refresh token to an httpOnly cookie
 *   issued directly by the backend instead.
 */
let accessToken: string | null = null;
const REFRESH_TOKEN_KEY = "knowsphere_refresh_token";

export function setAccessToken(token: string | null) {
  accessToken = token;
}
export function getAccessToken() {
  return accessToken;
}
export function setRefreshToken(token: string | null) {
  if (token) localStorage.setItem(REFRESH_TOKEN_KEY, token);
  else localStorage.removeItem(REFRESH_TOKEN_KEY);
}
export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}
export function clearTokens() {
  accessToken = null;
  setRefreshToken(null);
}

export const apiClient = axios.create({ baseURL: API_BASE_URL });

// Separate instance for the refresh call itself, so it never gets caught
// in the response interceptor's own retry loop.
const refreshClient = axios.create({ baseURL: API_BASE_URL });

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

let refreshPromise: Promise<string | null> | null = null;

export async function refreshAccessToken(): Promise<string | null> {
  return performRefresh();
}

async function performRefresh(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  try {
    const res = await refreshClient.post<ApiResponse<Pick<LoginResponse, "access_token" | "refresh_token">>>(
      "/auth/refresh",
      {},
      { headers: { Authorization: `Bearer ${refreshToken}` } }
    );
    if (res.data.success) {
      setAccessToken(res.data.data.access_token);
      setRefreshToken(res.data.data.refresh_token);
      return res.data.data.access_token;
    }
    return null;
  } catch {
    return null;
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiResponse<unknown>>) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
    const errorCode = error.response?.data && !error.response.data.success ? error.response.data.error.code : null;

    const isExpired = error.response?.status === 401 && errorCode === "TOKEN_EXPIRED";

    if (isExpired && original && !original._retried) {
      original._retried = true;

      // De-dupe concurrent refreshes: if one is already in flight, reuse it.
      if (!refreshPromise) {
        refreshPromise = performRefresh().finally(() => {
          refreshPromise = null;
        });
      }
      const newToken = await refreshPromise;

      if (newToken) {
        original.headers = original.headers ?? {};
        original.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(original);
      }

      // Refresh failed — clear session and let AuthContext react.
      clearTokens();
      window.dispatchEvent(new Event("knowsphere:auth-expired"));
    }

    return Promise.reject(error);
  }
);
