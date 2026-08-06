import { apiClient } from "@/api/client";
import type { ApiResponse, AuditLogEntry } from "@/types";

export interface AuditLogFilters {
  action?: string;
  actor_email?: string;
  resource_type?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export interface AuditLogListResponse {
  logs: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

export async function listAuditLogs(filters: AuditLogFilters = {}) {
  const res = await apiClient.get<ApiResponse<AuditLogListResponse>>("/audit", { params: filters });
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function listActionTypes() {
  const res = await apiClient.get<ApiResponse<string[]>>("/audit/action-types");
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}
