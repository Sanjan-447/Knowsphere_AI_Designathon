import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import * as documentsApi from "@/api/documents";
import type { KnowledgeDocument, UploadResultItem } from "@/types";
import { DocumentDrawer } from "@/components/documents/DocumentDrawer";

const STATUS_STYLES: Record<string, string> = {
  ready: "bg-teal/10 text-teal",
  failed: "bg-danger/10 text-danger",
  uploaded: "bg-paper-dim text-[#6B6558]",
  validating: "bg-gold-soft text-[#6B4E15]",
  parsing: "bg-gold-soft text-[#6B4E15]",
  chunking: "bg-gold-soft text-[#6B4E15]",
  embedding: "bg-gold-soft text-[#6B4E15]",
  indexing: "bg-gold-soft text-[#6B4E15]",
};

const IN_PROGRESS_STATUSES = ["uploaded", "validating", "parsing", "chunking", "embedding", "indexing"];

const FILE_TYPES = ["pdf", "docx", "txt", "md", "csv", "xlsx", "json", "eml", "msg"];
const SOURCE_TYPES = ["upload", "email", "chat_export", "share_link"];

export function DocumentsPage() {
  const { user } = useAuth();
  const canManage = user?.role === "admin" || user?.role === "manager";

  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [fileType, setFileType] = useState("");
  const [sourceType, setSourceType] = useState("");

  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadResults, setUploadResults] = useState<UploadResultItem[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedDoc, setSelectedDoc] = useState<KnowledgeDocument | null>(null);

  async function loadDocuments() {
    setError(null);
    try {
      const data = await documentsApi.listDocuments({
        search: search || undefined,
        file_type: fileType || undefined,
        source_type: sourceType || undefined,
        page_size: 100,
      });
      setDocuments(data.documents);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadDocuments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, fileType, sourceType]);

  // Poll while any visible document is still processing.
  useEffect(() => {
    const hasInFlight = documents.some((d) => IN_PROGRESS_STATUSES.includes(d.status));
    if (!hasInFlight) return;
    const interval = setInterval(loadDocuments, 3000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documents]);

  function flashBanner(message: string) {
    setBanner(message);
    setTimeout(() => setBanner(null), 4000);
  }

  async function handleFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    const files = Array.from(fileList);
    setUploadProgress(0);
    setUploadResults([]);
    setError(null);
    try {
      const results = await documentsApi.uploadDocuments(files, {
        onProgress: setUploadProgress,
      });
      setUploadResults(results);
      const accepted = results.filter((r) => r.status === "accepted").length;
      const duplicates = results.filter((r) => r.status === "duplicate").length;
      const rejected = results.filter((r) => r.status === "rejected").length;
      flashBanner(
        `${accepted} file(s) accepted for processing` +
          (duplicates ? `, ${duplicates} duplicate(s) skipped` : "") +
          (rejected ? `, ${rejected} rejected` : "") + "."
      );
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploadProgress(null);
    }
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleDelete(id: number) {
    if (!confirm("Delete this document and all its chunks? This cannot be undone.")) return;
    try {
      await documentsApi.deleteDocument(id);
      flashBanner("Document deleted.");
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.");
    }
  }

  async function handleReprocess(id: number) {
    try {
      await documentsApi.reprocessDocument(id);
      flashBanner("Reprocessing started.");
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reprocess failed.");
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-10 py-10">
      <div className="mb-6">
        <h1 className="font-display text-xl font-semibold text-ink">Document library</h1>
        <p className="mt-1 text-sm text-[#6B6558]">
          {canManage
            ? "Upload and manage the knowledge sources the assistant can draw from once retrieval is enabled."
            : "Browse the knowledge sources available to your role."}
        </p>
      </div>

      {banner && <div className="mb-4 rounded border border-teal/30 bg-teal/5 px-3 py-2 text-sm text-teal">{banner}</div>}
      {error && <div className="mb-4 rounded border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</div>}

      {canManage && (
        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`mb-6 flex cursor-pointer flex-col items-center justify-center rounded border-2 border-dashed px-6 py-10 text-center transition-colors ${
            isDragging ? "border-gold bg-gold-soft/40" : "border-rule bg-white/60 hover:border-gold"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
            accept=".pdf,.docx,.txt,.md,.csv,.xlsx,.json,.eml,.msg"
          />
          <p className="text-sm font-medium text-ink">Drag and drop files here, or click to browse</p>
          <p className="mt-1 text-xs text-[#6B6558]">
            PDF, DOCX, TXT, Markdown, CSV, XLSX, JSON, EML, MSG — up to 50MB each
          </p>
          {uploadProgress !== null && (
            <div className="mt-4 w-64">
              <div className="h-2 overflow-hidden rounded-full bg-paper-dim">
                <div className="h-full bg-gold transition-all" style={{ width: `${uploadProgress}%` }} />
              </div>
              <p className="mt-1 text-xs text-[#6B6558]">Uploading… {uploadProgress}%</p>
            </div>
          )}
          {uploadResults.length > 0 && uploadProgress === null && (
            <div className="mt-4 space-y-1 text-left text-xs">
              {uploadResults.map((r, i) => (
                <div key={i} className={r.status === "accepted" ? "text-teal" : r.status === "duplicate" ? "text-[#6B6558]" : "text-danger"}>
                  {r.filename}: {r.message || r.status}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by title…"
          className="flex-1 min-w-[180px] rounded border border-rule px-3 py-2 text-sm focus:border-gold focus:outline-none"
        />
        <select
          value={fileType}
          onChange={(e) => setFileType(e.target.value)}
          className="rounded border border-rule bg-white px-3 py-2 text-sm focus:border-gold focus:outline-none"
        >
          <option value="">All file types</option>
          {FILE_TYPES.map((t) => <option key={t} value={t}>{t.toUpperCase()}</option>)}
        </select>
        <select
          value={sourceType}
          onChange={(e) => setSourceType(e.target.value)}
          className="rounded border border-rule bg-white px-3 py-2 text-sm focus:border-gold focus:outline-none"
        >
          <option value="">All sources</option>
          {SOURCE_TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
        </select>
      </div>

      {isLoading ? (
        <p className="text-sm text-[#6B6558]">Loading documents…</p>
      ) : documents.length === 0 ? (
        <p className="rounded border border-dashed border-rule bg-white/60 px-4 py-8 text-center text-sm text-[#6B6558]">
          No documents match your filters yet.
        </p>
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-[#6B6558]">{total} document{total !== 1 ? "s" : ""}</p>
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center justify-between gap-4 rounded border border-rule bg-white px-4 py-3 hover:border-gold"
            >
              <button onClick={() => setSelectedDoc(doc)} className="flex min-w-0 flex-1 items-center gap-3 text-left">
                <span className="flex-shrink-0 rounded bg-ink px-2 py-0.5 font-mono text-[10px] text-gold">
                  {doc.file_type}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-ink">{doc.title}</span>
                  <span className="block text-xs text-[#6B6558]">
                    {doc.department || "No department"} · {doc.chunk_count ?? 0} chunks · v{doc.version}
                  </span>
                </span>
                <span className={`flex-shrink-0 rounded px-2 py-1 text-[11px] font-medium ${STATUS_STYLES[doc.status] || ""}`}>
                  {doc.status}
                </span>
              </button>
              {canManage && (
                <div className="flex flex-shrink-0 gap-2 text-xs">
                  <button
                    onClick={() => handleReprocess(doc.id)}
                    className="rounded border border-rule px-2.5 py-1.5 font-medium text-ink hover:bg-paper-dim"
                  >
                    Reprocess
                  </button>
                  <button
                    onClick={() => handleDelete(doc.id)}
                    className="rounded border border-danger/40 px-2.5 py-1.5 font-medium text-danger hover:bg-danger/5"
                  >
                    Delete
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <DocumentDrawer document={selectedDoc} onClose={() => setSelectedDoc(null)} />
    </div>
  );
}
