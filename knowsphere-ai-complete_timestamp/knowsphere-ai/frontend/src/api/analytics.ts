import { apiClient } from "@/api/client";
import type {
  ApiResponse, OverviewStats, TrendPoint, TopicCount, FrequentDocument, DepartmentUsage,
  ProviderUsageStat, FeedbackSummary, AnalyticsFilters, UnansweredQuestion, LowConfidenceResponse,
  NeverRetrievedDocument, StaleDocument, DuplicateDocumentGroup, KnowledgeCoverage,
} from "@/types";

async function get<T>(path: string, params: Record<string, unknown> = {}): Promise<T> {
  const res = await apiClient.get<ApiResponse<T>>(path, { params: params as Record<string, unknown> });
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export const getOverview = () => get<OverviewStats>("/analytics/overview");
export const getTrends = (granularity: "day" | "week" | "month", filters: AnalyticsFilters = {}) =>
  get<TrendPoint[]>("/analytics/trends", { granularity, ...filters });
export const getTopics = (limit = 20, filters: AnalyticsFilters = {}) =>
  get<TopicCount[]>("/analytics/topics", { limit, ...filters });
export const getFrequentDocuments = (limit = 20, filters: AnalyticsFilters = {}) =>
  get<FrequentDocument[]>("/analytics/documents", { limit, ...filters });
export const getDepartmentUsage = (filters: AnalyticsFilters = {}) =>
  get<DepartmentUsage[]>("/analytics/departments", filters);
export const getProviderUsageDistribution = (filters: AnalyticsFilters = {}) =>
  get<ProviderUsageStat[]>("/analytics/providers", filters);
export const getFeedbackSummary = (filters: AnalyticsFilters = {}) =>
  get<FeedbackSummary>("/analytics/feedback", filters);

// --- Knowledge Intelligence ---
export const getUnansweredQuestions = (limit = 50) =>
  get<UnansweredQuestion[]>("/analytics/knowledge/unanswered-questions", { limit });
export const getMissingKnowledgeAreas = (limit = 20) =>
  get<TopicCount[]>("/analytics/knowledge/missing-areas", { limit });
export const getLowConfidenceResponses = (threshold = 0.3, limit = 50) =>
  get<LowConfidenceResponse[]>("/analytics/knowledge/low-confidence", { threshold, limit });
export const getNeverRetrievedDocuments = () =>
  get<NeverRetrievedDocument[]>("/analytics/knowledge/never-retrieved");
export const getDuplicateDocuments = () =>
  get<DuplicateDocumentGroup[]>("/analytics/knowledge/duplicates");
export const getStaleDocuments = (days = 180) =>
  get<StaleDocument[]>("/analytics/knowledge/stale", { days });
export const getExpiredPolicies = (days = 365) =>
  get<StaleDocument[]>("/analytics/knowledge/expired-policies", { days });
export const getKnowledgeCoverage = () => get<KnowledgeCoverage>("/analytics/knowledge/coverage");

// --- Export ---
// These endpoints require the Authorization header, so a plain <a href>
// won't work (the browser wouldn't attach the JWT) — fetch as a blob
// through the authenticated apiClient instead, then trigger the download
// via a temporary object URL.
const EXTENSIONS: Record<string, string> = { csv: "csv", excel: "xlsx", pdf: "pdf" };

export async function downloadExport(
  path: string, format: "csv" | "excel" | "pdf", filenamePrefix: string
): Promise<void> {
  const res = await apiClient.get(path, { params: { format }, responseType: "blob" });
  const blob = new Blob([res.data as Blob]);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${filenamePrefix}.${EXTENSIONS[format]}`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export const downloadAnalyticsReport = (
  reportType: "overview" | "usage" | "feedback" | "knowledge-gaps", format: "csv" | "excel" | "pdf"
) => downloadExport(`/analytics/export/${reportType}`, format, `${reportType}_report`);

export const downloadAuditExport = (format: "csv" | "excel" | "pdf") =>
  downloadExport("/audit/export", format, "audit_log_export");
