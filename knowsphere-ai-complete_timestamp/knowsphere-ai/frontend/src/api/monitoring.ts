import { apiClient } from "@/api/client";
import type { ApiResponse, SystemStatus, ProviderMonitoringStat, LangSmithConfig } from "@/types";

export async function getSystemStatus() {
  const res = await apiClient.get<ApiResponse<SystemStatus>>("/observability/system");
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function getProviderMonitoring() {
  const res = await apiClient.get<ApiResponse<ProviderMonitoringStat[]>>("/observability/providers");
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function getLangSmithConfig() {
  const res = await apiClient.get<ApiResponse<LangSmithConfig>>("/observability/langsmith");
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function updateLangSmithConfig(payload: {
  api_key?: string; project_name?: string; endpoint?: string; tracing_enabled?: boolean;
}) {
  const res = await apiClient.patch<ApiResponse<LangSmithConfig>>("/observability/langsmith", payload);
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function testLangSmithConnection() {
  const res = await apiClient.post<ApiResponse<LangSmithConfig>>("/observability/langsmith/test-connection");
  if (!res.data.success) throw new Error(res.data.error.message);
  return { data: res.data.data, message: res.data.message };
}
