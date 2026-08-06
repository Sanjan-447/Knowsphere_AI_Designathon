import { apiClient } from "@/api/client";
import type {
  ApiResponse, KnowledgeDocument, DocumentListResponse, UploadResultItem,
} from "@/types";

export interface ListDocumentsParams {
  search?: string;
  file_type?: string;
  source_type?: string;
  status?: string;
  page?: number;
  page_size?: number;
}

export async function listDocuments(params: ListDocumentsParams = {}) {
  const res = await apiClient.get<ApiResponse<DocumentListResponse>>("/documents", { params });
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function getDocument(id: number) {
  const res = await apiClient.get<ApiResponse<KnowledgeDocument>>(`/documents/${id}`);
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function getDocumentStatus(id: number) {
  const res = await apiClient.get<ApiResponse<{ document_id: number; status: string; error_message: string | null; events: unknown[] }>>(
    `/documents/${id}/status`
  );
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function previewDocument(id: number) {
  const res = await apiClient.get<ApiResponse<{ preview_text: string; truncated: boolean }>>(
    `/documents/${id}/preview`
  );
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export interface UploadOptions {
  department?: string;
  tags?: string[];
  visibleToRoles?: string[];
  overwriteDuplicates?: boolean;
  onProgress?: (percent: number) => void;
}

export async function uploadDocuments(files: File[], options: UploadOptions = {}) {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  if (options.department) form.append("department", options.department);
  (options.tags || []).forEach((t) => form.append("tags", t));
  (options.visibleToRoles || []).forEach((r) => form.append("visible_to_roles", r));
  if (options.overwriteDuplicates) form.append("overwrite_duplicates", "true");

  const res = await apiClient.post<ApiResponse<{ results: UploadResultItem[] }>>("/documents", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (evt) => {
      if (options.onProgress && evt.total) {
        options.onProgress(Math.round((evt.loaded / evt.total) * 100));
      }
    },
  });
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data.results;
}

export async function uploadShareLink(url: string, options: UploadOptions & { bearerToken?: string } = {}) {
  const res = await apiClient.post<ApiResponse<{ document_id?: number; status: string }>>("/documents/share-link", {
    url,
    bearer_token: options.bearerToken,
    department: options.department,
    tags: options.tags,
    visible_to_roles: options.visibleToRoles,
  });
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function uploadChatExport(file: File, options: UploadOptions = {}) {
  const form = new FormData();
  form.append("file", file);
  if (options.department) form.append("department", options.department);
  (options.tags || []).forEach((t) => form.append("tags", t));
  (options.visibleToRoles || []).forEach((r) => form.append("visible_to_roles", r));

  const res = await apiClient.post<ApiResponse<{ document_id: number; status: string }>>(
    "/documents/chat-export", form, { headers: { "Content-Type": "multipart/form-data" } }
  );
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function deleteDocument(id: number) {
  const res = await apiClient.delete<ApiResponse<null>>(`/documents/${id}`);
  if (!res.data.success) throw new Error(res.data.error.message);
}

export async function reprocessDocument(id: number) {
  const res = await apiClient.post<ApiResponse<null>>(`/documents/${id}/reprocess`);
  if (!res.data.success) throw new Error(res.data.error.message);
}

export async function reuploadDocument(id: number, file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await apiClient.post<ApiResponse<KnowledgeDocument>>(`/documents/${id}/reupload`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}
