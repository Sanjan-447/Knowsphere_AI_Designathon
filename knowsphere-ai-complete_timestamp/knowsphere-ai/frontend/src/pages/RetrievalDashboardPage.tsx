import { useEffect, useState } from "react";
import * as chatApi from "@/api/chat";
import type { InspectedMessage } from "@/types";

interface RetrievedDoc {
  document_id: number;
  document_title: string;
  similarity_score: number;
  source_type: string;
}

interface RetrievalRow {
  message_id: number;
  session_id: number;
  user_email: string | null;
  question: string | null;
  response_preview: string;
  provider_used: string | null;
  model_used: string | null;
  latency_ms: number | null;
  retrieval_metadata: {
    retrieval_time_ms: number;
    embedding_model: string;
    top_k: number;
    chunks_considered: number;
    context_tokens: number;
    retrieved: RetrievedDoc[];
  } | null;
  citation_count: number;
  created_at: string;
}

export function RetrievalDashboardPage() {
  const [rows, setRows] = useState<RetrievalRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [inspected, setInspected] = useState<InspectedMessage | null>(null);
  const [inspecting, setInspecting] = useState(false);

  useEffect(() => {
    chatApi
      .fetchRecentRetrievals(50)
      .then((data) => setRows(data.results as RetrievalRow[]))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load."))
      .finally(() => setIsLoading(false));
  }, []);

  async function handleInspect(messageId: number) {
    setInspecting(true);
    setInspected(null);
    try {
      setInspected(await chatApi.inspectMessage(messageId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load inspector detail.");
    } finally {
      setInspecting(false);
    }
  }

  const avgRetrievalMs = rows.length
    ? Math.round(rows.reduce((sum, r) => sum + (r.retrieval_metadata?.retrieval_time_ms || 0), 0) / rows.length)
    : 0;
  const avgTokens = rows.length
    ? Math.round(rows.reduce((sum, r) => sum + (r.retrieval_metadata?.context_tokens || 0), 0) / rows.length)
    : 0;

  return (
    <div className="mx-auto max-w-4xl px-10 py-10">
      <h1 className="font-display text-xl font-semibold text-ink">Retrieval dashboard</h1>
      <p className="mt-1 text-sm text-[#6B6558]">
        Recent queries org-wide, for debugging retrieval quality and administrator visibility.
      </p>

      <div className="mb-6 mt-6 flex gap-4">
        <div className="flex-1 rounded border border-rule bg-white p-4">
          <div className="font-display text-2xl font-semibold text-ink">{rows.length}</div>
          <div className="text-xs text-[#6B6558]">Recent queries shown</div>
        </div>
        <div className="flex-1 rounded border border-rule bg-white p-4">
          <div className="font-display text-2xl font-semibold text-ink">{avgRetrievalMs}ms</div>
          <div className="text-xs text-[#6B6558]">Avg retrieval time</div>
        </div>
        <div className="flex-1 rounded border border-rule bg-white p-4">
          <div className="font-display text-2xl font-semibold text-ink">{avgTokens}</div>
          <div className="text-xs text-[#6B6558]">Avg context tokens</div>
        </div>
      </div>

      {error && <div className="mb-4 rounded border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</div>}
      {isLoading ? (
        <p className="text-sm text-[#6B6558]">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="rounded border border-dashed border-rule bg-white/60 px-4 py-8 text-center text-sm text-[#6B6558]">
          No queries yet.
        </p>
      ) : (
        <div className="space-y-2">
          {rows.map((row) => (
            <div key={row.message_id} className="rounded border border-rule bg-white">
              <button
                onClick={() => setExpandedId(expandedId === row.message_id ? null : row.message_id)}
                className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium text-ink">{row.question || "(no question)"}</div>
                  <div className="text-xs text-[#6B6558]">
                    {row.user_email} · {row.provider_used}/{row.model_used} · {row.citation_count} citation
                    {row.citation_count !== 1 ? "s" : ""}
                  </div>
                </div>
                <div className="flex-shrink-0 font-mono text-xs text-[#6B6558]">
                  {row.retrieval_metadata?.retrieval_time_ms ?? "—"}ms
                </div>
              </button>

              {expandedId === row.message_id && row.retrieval_metadata && (
                <div className="border-t border-rule bg-paper-dim px-4 py-3 text-xs">
                  <div className="mb-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
                    <div><span className="text-[#6B6558]">Embedding model:</span> {row.retrieval_metadata.embedding_model}</div>
                    <div><span className="text-[#6B6558]">Top-K:</span> {row.retrieval_metadata.top_k}</div>
                    <div><span className="text-[#6B6558]">Chunks considered:</span> {row.retrieval_metadata.chunks_considered}</div>
                    <div><span className="text-[#6B6558]">Context tokens:</span> {row.retrieval_metadata.context_tokens}</div>
                  </div>
                  <div className="mb-1 font-semibold text-ink">Retrieved documents</div>
                  <table className="w-full text-left">
                    <thead>
                      <tr className="text-[#6B6558]">
                        <th className="py-1">Document</th>
                        <th className="py-1">Source</th>
                        <th className="py-1">Similarity</th>
                      </tr>
                    </thead>
                    <tbody>
                      {row.retrieval_metadata.retrieved.map((doc, i) => (
                        <tr key={i} className="border-t border-rule/50">
                          <td className="py-1 pr-2">{doc.document_title}</td>
                          <td className="py-1 pr-2">{doc.source_type}</td>
                          <td className="py-1 font-mono">{(doc.similarity_score * 100).toFixed(1)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  <button
                    onClick={() => handleInspect(row.message_id)}
                    className="mt-3 rounded border border-gold px-2.5 py-1 text-[11px] font-medium text-gold hover:bg-gold-soft"
                  >
                    {inspecting ? "Loading…" : "Open full inspector (prompt + context)"}
                  </button>

                  {inspected && inspected.message_id === row.message_id && (
                    <div className="mt-3 space-y-3 rounded border border-gold bg-white p-3">
                      <div>
                        <div className="mb-1 text-[11px] font-semibold uppercase text-[#6B6558]">Final rendered context</div>
                        <pre className="max-h-40 overflow-y-auto whitespace-pre-wrap rounded bg-paper-dim p-2 text-[11px]">
                          {inspected.final_context || "(empty context)"}
                        </pre>
                      </div>
                      <div>
                        <div className="mb-1 text-[11px] font-semibold uppercase text-[#6B6558]">Generated prompt (admin-only)</div>
                        {inspected.generated_prompt?.map((m, i) => (
                          <div key={i} className="mb-1 rounded bg-paper-dim p-2 text-[11px]">
                            <span className="font-mono text-gold">[{m.role}]</span>{" "}
                            <span className="whitespace-pre-wrap">{m.content}</span>
                          </div>
                        ))}
                      </div>
                      <div className="text-[11px] text-[#6B6558]">
                        {inspected.prompt_tokens} prompt tokens · {inspected.completion_tokens} completion tokens ·{" "}
                        {inspected.had_error ? "had error" : "no error"} · served from cache: {String(inspected.served_from_cache)}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
