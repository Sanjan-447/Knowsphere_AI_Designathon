import { apiClient, getAccessToken } from "@/api/client";
import type { ApiResponse, ChatSessionType, SendMessageResponse } from "@/types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api/v1";

export async function createSession(title?: string) {
  const res = await apiClient.post<ApiResponse<ChatSessionType>>("/chat/sessions", { title });
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function listSessions() {
  const res = await apiClient.get<ApiResponse<ChatSessionType[]>>("/chat/sessions");
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function getSession(id: number) {
  const res = await apiClient.get<ApiResponse<ChatSessionType>>(`/chat/sessions/${id}`);
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function renameSession(id: number, title: string) {
  const res = await apiClient.patch<ApiResponse<ChatSessionType>>(`/chat/sessions/${id}`, { title });
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export async function deleteSession(id: number) {
  const res = await apiClient.delete<ApiResponse<null>>(`/chat/sessions/${id}`);
  if (!res.data.success) throw new Error(res.data.error.message);
}

export async function sendMessage(sessionId: number, message: string, topK = 8) {
  const res = await apiClient.post<ApiResponse<SendMessageResponse>>(
    `/chat/sessions/${sessionId}/messages`, { message, top_k: topK }
  );
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

export interface StreamCallbacks {
  onChunk: (text: string) => void;
  onDone: (finalMessage: unknown) => void;
  onError: (error: string) => void;
}

/**
 * Consumes the SSE streaming endpoint via fetch's ReadableStream — axios
 * doesn't handle text/event-stream well in the browser, so this bypasses
 * the shared apiClient and attaches the auth header manually. Does not
 * go through apiClient's automatic-refresh interceptor; a 401 here simply
 * surfaces as a stream error (acceptable since access tokens are short-lived
 * and a chat message is a low-stakes place to ask the user to retry).
 */
export async function streamMessage(sessionId: number, message: string, topK: number, callbacks: StreamCallbacks) {
  const token = getAccessToken();
  try {
    const response = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}/messages/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message, top_k: topK }),
    });

    if (!response.ok || !response.body) {
      callbacks.onError(`Request failed (${response.status})`);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split("\n\n");
      buffer = events.pop() || "";

      for (const event of events) {
        const line = event.trim();
        if (!line.startsWith("data:")) continue;
        const payload = line.slice("data:".length).trim();
        try {
          const parsed = JSON.parse(payload);
          if (parsed.type === "chunk") callbacks.onChunk(parsed.text);
          else if (parsed.type === "done") callbacks.onDone(parsed.message);
        } catch {
          // ignore malformed SSE lines
        }
      }
    }
  } catch (err) {
    callbacks.onError(err instanceof Error ? err.message : "Streaming connection failed.");
  }
}

export async function fetchRecentRetrievals(limit = 50) {
  const res = await apiClient.get<ApiResponse<{ results: unknown[]; count: number }>>(
    "/chat/admin/recent-retrievals", { params: { limit } }
  );
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

// --- Feedback (Phase 5) ---
export async function submitFeedback(messageId: number, rating: "helpful" | "not_helpful", comment?: string) {
  const res = await apiClient.post<ApiResponse<{ id: number; rating: string; comment: string | null }>>(
    `/chat/messages/${messageId}/feedback`, { rating, comment }
  );
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}

// --- Retrieval Inspector (Phase 5, admin-only) ---
export async function inspectMessage(messageId: number) {
  const res = await apiClient.get<ApiResponse<import("@/types").InspectedMessage>>(
    `/chat/admin/messages/${messageId}/inspect`
  );
  if (!res.data.success) throw new Error(res.data.error.message);
  return res.data.data;
}
