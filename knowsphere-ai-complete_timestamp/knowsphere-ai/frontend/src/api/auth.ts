import { apiClient, getRefreshToken } from "@/api/client";
import type { ApiResponse, LoginResponse, User } from "@/types";

export async function login(email: string, password: string) {
  const res = await apiClient.post<ApiResponse<LoginResponse>>("/auth/login", { email, password });
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function logout() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return;
  try {
    await apiClient.post<ApiResponse<null>>(
      "/auth/logout",
      {},
      { headers: { Authorization: `Bearer ${refreshToken}` } }
    );
  } catch {
    // Best-effort — proceed with local logout regardless.
  }
}

export async function fetchMe() {
  const res = await apiClient.get<ApiResponse<User>>("/auth/me");
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

// --- Admin user management (Phase 5) ---
export async function listUsers() {
  const res = await apiClient.get<ApiResponse<User[]>>("/auth/users");
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function updateUser(userId: number, payload: { role?: string; is_active?: boolean }) {
  const res = await apiClient.patch<ApiResponse<User>>(`/auth/users/${userId}`, payload);
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function resetUserSessions(userId: number) {
  const res = await apiClient.post<ApiResponse<null>>(`/auth/users/${userId}/reset-sessions`);
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.message;
}

export async function createUser(payload: { email: string; password: string; display_name: string; role: string }) {
  const res = await apiClient.post<ApiResponse<User>>("/auth/users", payload);
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}
