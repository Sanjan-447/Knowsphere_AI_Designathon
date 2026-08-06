// Mirrors app/common/responses.py — every API call returns one of these two shapes.
export interface ApiSuccess<T> {
  success: true;
  data: T;
  message: string;
  request_id: string | null;
}

export interface ApiError {
  success: false;
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
  request_id: string | null;
}

export type ApiResponse<T> = ApiSuccess<T> | ApiError;

export type Role = "admin" | "manager" | "employee";

export interface User {
  id: number;
  email: string;
  display_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface LoginResponse {
  user: User;
  access_token: string;
  refresh_token: string;
}

export type ProviderType =
  | "openai"
  | "anthropic"
  | "gemini"
  | "groq"
  | "openrouter"
  | "nvidia_nim"
  | "ollama"
  | "openai_compatible";

export interface ProviderConfig {
  id: number;
  display_name: string;
  provider_type: ProviderType;
  api_key: string | null; // masked unless explicitly revealed
  base_url: string | null;
  extra_config: Record<string, unknown> | null;
  is_active: boolean;
  is_default: boolean;
  last_validated_at: string | null;
  last_validation_status: "passed" | "failed" | null;
  created_at: string;
  updated_at: string;
}

export interface SupportedProviderMeta {
  label: string;
  key_prefix: string | null;
  requires_base_url: boolean;
}

// --- Phase 2: Documents ---

export type DocumentStatus =
  | "uploaded"
  | "validating"
  | "parsing"
  | "chunking"
  | "embedding"
  | "indexing"
  | "ready"
  | "failed";

export type SourceType = "upload" | "email" | "chat_export" | "share_link";

export interface ProcessingEvent {
  stage: string;
  message: string | null;
  created_at: string;
}

export interface DocumentMetadataEntry {
  key: string;
  value: string;
}

export interface KnowledgeDocument {
  id: number;
  document_uid: string;
  title: string;
  original_filename: string | null;
  file_type: string;
  source_type: SourceType;
  file_size_bytes: number | null;
  department: string | null;
  author: string | null;
  version: number;
  tags: string[];
  source_last_modified: string | null;
  status: DocumentStatus;
  error_message: string | null;
  visible_to_roles: string[];
  created_at: string;
  updated_at: string;
  chunk_count?: number;
  metadata?: DocumentMetadataEntry[];
  processing_events?: ProcessingEvent[];
}

export interface DocumentListResponse {
  documents: KnowledgeDocument[];
  total: number;
  page: number;
  page_size: number;
}

export interface UploadResultItem {
  filename: string;
  status: "accepted" | "rejected" | "duplicate";
  document_id?: number;
  existing_document_id?: number;
  message?: string;
}

// --- Phase 3: Chat ---

export interface CitationDisplayFields {
  document_name?: string;
  page?: number | null;
  section?: string | null;
  subject?: string;
  sender?: string | null;
  date?: string | null;
  channel?: string;
  timestamp?: string;
  file_name?: string;
  source?: string;
}

export interface Citation {
  marker: number;
  document_id: number | null;
  chunk_id: number | null;
  citation_type: "document" | "email" | "chat_export" | "share_link";
  display_fields: CitationDisplayFields;
  snippet: string | null;
  confidence_score: number | null;
}

export interface RetrievedChunkInfo {
  document_id: number;
  document_title: string;
  similarity_score: number;
  source_type: string;
}

export interface RetrievalMetadata {
  retrieval_time_ms: number;
  embedding_model: string;
  top_k: number;
  chunks_considered: number;
  context_truncated: boolean;
  context_tokens: number;
  injection_flagged: boolean;
  retrieved: RetrievedChunkInfo[];
}

export interface ChatMessageType {
  id: number;
  session_id: number;
  role: "user" | "assistant";
  content: string;
  provider_used: string | null;
  model_used: string | null;
  created_at: string;
  citations: Citation[];
  retrieval_metadata?: RetrievalMetadata;
  prompt_tokens?: number;
  completion_tokens?: number;
  latency_ms?: number;
}

export interface ChatSessionType {
  id: number;
  session_uid: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  messages?: ChatMessageType[];
}

export interface SendMessageResponse {
  response: string;
  citations: Citation[];
  provider_used: string;
  model_used: string;
  latency_ms: number;
  from_cache: boolean;
  retrieval: RetrievalMetadata;
}

// --- Phase 5: Analytics ---

export interface OverviewStats {
  total_users: number;
  active_users: number;
  uploaded_documents: number;
  indexed_chunks: number;
  chat_sessions: number;
  total_queries: number;
  avg_response_time_ms: number;
  avg_retrieval_time_ms: number;
  cache_hit_rate: number;
  total_tokens_consumed: number;
  estimated_api_cost_usd: number;
}

export interface TrendPoint {
  date: string;
  query_count: number;
  avg_response_time_ms: number;
  avg_retrieval_time_ms: number;
  total_tokens: number;
}

export interface TopicCount {
  term: string;
  count: number;
}

export interface FrequentDocument {
  document_id: number;
  title: string;
  citation_count: number;
}

export interface DepartmentUsage {
  department: string;
  citation_count: number;
}

export interface ProviderUsageStat {
  provider: string;
  query_count: number;
  avg_latency_ms: number;
}

export interface FeedbackSummary {
  total_feedback: number;
  helpful: number;
  not_helpful: number;
  helpful_rate: number | null;
}

export interface AnalyticsFilters {
  date_from?: string;
  date_to?: string;
  department?: string;
  user_id?: number;
  provider?: string;
  [key: string]: unknown;
}

// --- Phase 5: Knowledge Intelligence ---

export interface UnansweredQuestion {
  message_id: number;
  question: string | null;
  created_at: string;
}

export interface LowConfidenceResponse {
  message_id: number;
  content: string;
  max_confidence: number;
  citation_count: number;
  created_at: string;
}

export interface NeverRetrievedDocument {
  document_id: number;
  title: string;
  department: string | null;
  created_at: string;
}

export interface StaleDocument {
  document_id: number;
  title: string;
  department: string | null;
  last_updated: string;
  days_since_update: number;
}

export interface DuplicateDocumentGroup {
  content_hash: string;
  count: number;
  documents: { id: number; title: string; created_at: string }[];
}

export interface KnowledgeCoverage {
  total_documents: number;
  total_chunks: number;
  documents_ever_retrieved: number;
  documents_never_retrieved: number;
  coverage_rate: number | null;
  by_department: Record<string, number>;
  by_source_type: Record<string, number>;
  by_file_type: Record<string, number>;
}

// --- Phase 5: System & Provider Monitoring ---

export interface HealthCheckResult {
  status: "healthy" | "unhealthy";
  message: string;
  [key: string]: unknown;
}

export interface SystemStatus {
  overall_status: "healthy" | "degraded";
  postgresql: HealthCheckResult;
  pgvector: HealthCheckResult;
  redis: HealthCheckResult;
  celery: HealthCheckResult;
  storage: {
    disk_total_gb: number;
    disk_used_gb: number;
    disk_free_gb: number;
    disk_used_percent: number;
    upload_dir_size_mb: number;
  };
  resources: {
    cpu_percent: number;
    memory_percent: number;
    memory_used_mb: number;
    memory_total_mb: number;
  };
}

export interface ProviderMonitoringStat {
  provider_config_id: number;
  display_name: string;
  provider_type: string;
  is_active: boolean;
  is_default: boolean;
  query_count: number;
  success_rate: number | null;
  error_rate: number | null;
  avg_response_time_ms: number;
  total_tokens: number;
  estimated_cost_usd: number;
  last_used: string | null;
  last_validation_status: string | null;
}

// --- Phase 5: Audit ---

export interface AuditLogEntry {
  id: number;
  actor_user_id: number | null;
  actor_email: string | null;
  actor_role: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  details: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}

// --- Phase 5: Notifications ---

export interface NotificationEntry {
  id: number;
  notification_type: string;
  severity: "info" | "warning" | "error";
  title: string;
  message: string | null;
  resource_type: string | null;
  resource_id: string | null;
  extra: Record<string, unknown>;
  is_read: boolean;
  created_at: string;
}

// --- Phase 5: Retrieval Inspector ---

export interface InspectedMessage {
  message_id: number;
  session_id: number;
  content: string;
  provider_used: string | null;
  model_used: string | null;
  had_error: boolean;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  latency_ms: number | null;
  retrieved_chunks: RetrievedChunkInfo[];
  retrieval_time_ms: number | null;
  embedding_model: string | null;
  context_tokens: number | null;
  context_truncated: boolean | null;
  final_context: string | null;
  generated_prompt: { role: string; content: string }[] | null;
  citations: Citation[];
  served_from_cache: boolean;
  created_at: string;
}

// --- Phase 5: LangSmith / Observability ---

export interface LangSmithConfig {
  id: number;
  api_key: string | null;
  has_api_key: boolean;
  project_name: string;
  endpoint: string | null;
  tracing_enabled: boolean;
  last_test_at: string | null;
  last_test_status: "passed" | "failed" | null;
  last_test_message: string | null;
  updated_at: string;
}

// --- Phase 5: User Management ---

export interface AdminUserRow extends User {
  // User already has id, email, display_name, role, is_active, created_at, last_login_at
}
