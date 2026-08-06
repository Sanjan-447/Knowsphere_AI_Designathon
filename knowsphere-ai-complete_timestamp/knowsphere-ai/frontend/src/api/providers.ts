import { apiClient } from "@/api/client";
import type { ApiResponse, ProviderConfig, SupportedProviderMeta } from "@/types";

export async function listSupportedProviderTypes() {
  const res = await apiClient.get<ApiResponse<Record<string, SupportedProviderMeta>>>(
    "/providers/supported-types"
  );
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function listProviders() {
  const res = await apiClient.get<ApiResponse<ProviderConfig[]>>("/providers");
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export interface CreateProviderInput {
  display_name: string;
  provider_type: string;
  api_key?: string;
  base_url?: string;
  extra_config?: Record<string, unknown>;
}

export async function createProvider(input: CreateProviderInput) {
  const res = await apiClient.post<ApiResponse<ProviderConfig>>("/providers", input);
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function updateProvider(id: number, input: Partial<CreateProviderInput> & { is_active?: boolean }) {
  const res = await apiClient.patch<ApiResponse<ProviderConfig>>(`/providers/${id}`, input);
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function deleteProvider(id: number) {
  const res = await apiClient.delete<ApiResponse<null>>(`/providers/${id}`);
  if (!res.data.success) throw new Error(res.data.error.message);
}

export async function validateProvider(id: number) {
  const res = await apiClient.post<ApiResponse<{ passed: boolean; errors: string[]; provider: ProviderConfig }>>(
    `/providers/${id}/validate`
  );
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function setDefaultProvider(id: number) {
  const res = await apiClient.post<ApiResponse<ProviderConfig>>(`/providers/${id}/activate`);
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}
