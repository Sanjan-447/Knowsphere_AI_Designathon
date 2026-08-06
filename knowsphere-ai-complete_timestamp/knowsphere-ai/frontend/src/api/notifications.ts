import { apiClient } from "@/api/client";
import type { ApiResponse, NotificationEntry } from "@/types";

export interface NotificationListResponse {
  notifications: NotificationEntry[];
  total: number;
  unread_count: number;
  page: number;
  page_size: number;
}

export async function listNotifications(unreadOnly = false, page = 1) {
  const res = await apiClient.get<ApiResponse<NotificationListResponse>>("/notifications", {
    params: { unread_only: unreadOnly, page },
  });
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function markNotificationRead(id: number) {
  const res = await apiClient.patch<ApiResponse<NotificationEntry>>(`/notifications/${id}/read`);
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function markAllNotificationsRead() {
  const res = await apiClient.post<ApiResponse<null>>("/notifications/mark-all-read");
  if (!res.data.success) throw new Error(res.data.error.message);
}

export async function checkExpiredDocuments(daysThreshold = 365) {
  const res = await apiClient.post<ApiResponse<{ created: number }>>("/notifications/check-expired-documents", {
    days_threshold: daysThreshold,
  });
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}
