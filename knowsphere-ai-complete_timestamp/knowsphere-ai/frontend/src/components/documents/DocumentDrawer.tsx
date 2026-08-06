import { useEffect, useState } from "react";
import type { KnowledgeDocument } from "@/types";
import * as documentsApi from "@/api/documents";

interface Props {
  document: KnowledgeDocument | null;
  onClose: () => void;
}

const STAGE_LABELS: Record<string, string> = {
  uploaded: "Uploaded",
  validating: "Validating",
  parsing: "Parsing",
  chunking: "Chunking",
  embedding: "Embedding",
  indexing: "Indexing",
  ready: "Ready",
  failed: "Failed",
};

export function DocumentDrawer({ document, onClose }: Props) {
  const [full, setFull] = useState<KnowledgeDocument | null>(null);
  const [previewText, setPreviewText] = useState<string>("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!document) return;
    setLoading(true);
    Promise.all([documentsApi.getDocument(document.id), documentsApi.previewDocument(document.id)])
      .then(([doc, preview]) => {
        setFull(doc);
        setPreviewText(preview.preview_text);
      })
      .finally(() => setLoading(false));
  }, [document]);

  const isOpen = !!document;

  return (
    <>
      <div
        className={`fixed inset-0 z-10 bg-ink/25 transition-opacity ${isOpen ? "opacity-100" : "pointer-events-none opacity-0"}`}
        onClick={onClose}
      />
      <div
        className={`fixed right-0 top-0 z-20 h-full w-[420px] transform border-l border-rule bg-paper shadow-xl transition-transform ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {document && (
          <div className="flex h-full flex-col">
            <div className="flex items-start justify-between border-b border-rule px-6 py-5">
              <div className="min-w-0">
                <div className="font-mono text-[11px] uppercase text-gold">{document.file_type}</div>
                <div className="mt-1 truncate font-display text-base font-semibold text-ink">{document.title}</div>
                <div className="mt-0.5 text-xs text-[#6B6558]">v{document.version} · {document.source_type}</div>
              </div>
              <button onClick={onClose} className="text-lg text-[#6B6558] hover:text-ink">✕</button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-5 text-sm">
              {loading && <p className="text-[#6B6558]">Loading…</p>}

              {!loading && full && (
                <>
                  <section className="mb-6">
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[#6B6558]">
                      Processing history
                    </h3>
                    <ol className="space-y-2 border-l-2 border-rule pl-4">
                      {(full.processing_events || []).map((e, i) => (
                        <li key={i} className="relative">
                          <span className="absolute -left-[21px] top-1 h-2 w-2 rounded-full bg-gold" />
                          <div className="text-xs font-medium text-ink">{STAGE_LABELS[e.stage] || e.stage}</div>
                          {e.message && <div className="text-xs text-[#6B6558]">{e.message}</div>}
                        </li>
                      ))}
                    </ol>
                  </section>

                  <section className="mb-6">
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[#6B6558]">Metadata</h3>
                    <dl className="space-y-1 text-xs">
                      <div className="flex justify-between"><dt className="text-[#6B6558]">Department</dt><dd>{full.department || "—"}</dd></div>
                      <div className="flex justify-between"><dt className="text-[#6B6558]">Author</dt><dd>{full.author || "—"}</dd></div>
                      <div className="flex justify-between"><dt className="text-[#6B6558]">Size</dt><dd>{full.file_size_bytes ? `${(full.file_size_bytes / 1024).toFixed(1)} KB` : "—"}</dd></div>
                      <div className="flex justify-between"><dt className="text-[#6B6558]">Chunks</dt><dd>{full.chunk_count ?? "—"}</dd></div>
                      <div className="flex justify-between"><dt className="text-[#6B6558]">Visible to</dt><dd>{full.visible_to_roles.length ? full.visible_to_roles.join(", ") : "all roles"}</dd></div>
                      {(full.metadata || []).map((m) => (
                        <div key={m.key} className="flex justify-between gap-3">
                          <dt className="flex-shrink-0 text-[#6B6558]">{m.key}</dt>
                          <dd className="truncate text-right">{m.value}</dd>
                        </div>
                      ))}
                    </dl>
                    {full.tags.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {full.tags.map((t) => (
                          <span key={t} className="rounded bg-paper-dim px-2 py-0.5 text-[11px] text-[#6B6558]">{t}</span>
                        ))}
                      </div>
                    )}
                  </section>

                  {full.error_message && (
                    <section className="mb-6 rounded border border-danger/40 bg-danger/5 px-3 py-2 text-xs text-danger">
                      {full.error_message}
                    </section>
                  )}

                  <section>
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[#6B6558]">Content preview</h3>
                    <p className="whitespace-pre-line rounded border border-rule bg-white p-3 text-xs leading-relaxed text-[#3a3a3a]">
                      {previewText || "No preview available yet."}
                    </p>
                  </section>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
