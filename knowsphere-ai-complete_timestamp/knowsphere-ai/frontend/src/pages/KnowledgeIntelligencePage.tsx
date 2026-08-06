import { useEffect, useState } from "react";
import * as analyticsApi from "@/api/analytics";
import type {
  UnansweredQuestion, TopicCount, LowConfidenceResponse, NeverRetrievedDocument,
  StaleDocument, DuplicateDocumentGroup, KnowledgeCoverage,
} from "@/types";

type TabKey = "coverage" | "unanswered" | "low_confidence" | "never_retrieved" | "stale" | "duplicates";

const TABS: { key: TabKey; label: string }[] = [
  { key: "coverage", label: "Coverage" },
  { key: "unanswered", label: "Unanswered questions" },
  { key: "low_confidence", label: "Low confidence" },
  { key: "never_retrieved", label: "Never retrieved" },
  { key: "stale", label: "Stale documents" },
  { key: "duplicates", label: "Duplicates" },
];

export function KnowledgeIntelligencePage() {
  const [tab, setTab] = useState<TabKey>("coverage");
  const [coverage, setCoverage] = useState<KnowledgeCoverage | null>(null);
  const [unanswered, setUnanswered] = useState<UnansweredQuestion[]>([]);
  const [missingAreas, setMissingAreas] = useState<TopicCount[]>([]);
  const [lowConfidence, setLowConfidence] = useState<LowConfidenceResponse[]>([]);
  const [neverRetrieved, setNeverRetrieved] = useState<NeverRetrievedDocument[]>([]);
  const [stale, setStale] = useState<StaleDocument[]>([]);
  const [duplicates, setDuplicates] = useState<DuplicateDocumentGroup[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    setIsLoading(true);
    Promise.all([
      analyticsApi.getKnowledgeCoverage(),
      analyticsApi.getUnansweredQuestions(50),
      analyticsApi.getMissingKnowledgeAreas(15),
      analyticsApi.getLowConfidenceResponses(0.3, 50),
      analyticsApi.getNeverRetrievedDocuments(),
      analyticsApi.getStaleDocuments(180),
      analyticsApi.getDuplicateDocuments(),
    ])
      .then(([c, u, m, lc, nr, s, dup]) => {
        setCoverage(c);
        setUnanswered(u);
        setMissingAreas(m);
        setLowConfidence(lc);
        setNeverRetrieved(nr);
        setStale(s);
        setDuplicates(dup);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load."))
      .finally(() => setIsLoading(false));
  }, []);

  async function handleExport() {
    setExporting(true);
    try {
      await analyticsApi.downloadAnalyticsReport("knowledge-gaps", "pdf");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed.");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-10 py-10">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="font-display text-xl font-semibold text-ink">Knowledge Intelligence</h1>
          <p className="mt-1 text-sm text-[#6B6558]">
            Gaps and governance signals in your knowledge base — for administrators.
          </p>
        </div>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="rounded border border-rule px-3 py-1.5 text-xs font-medium text-ink hover:bg-paper-dim disabled:opacity-50"
        >
          {exporting ? "…" : "Export gap report (PDF)"}
        </button>
      </div>

      <div className="mb-5 flex flex-wrap gap-1 border-b border-rule">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-3 py-2 text-xs font-medium ${
              tab === t.key ? "border-b-2 border-gold text-ink" : "text-[#6B6558] hover:text-ink"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && <div className="mb-4 rounded border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</div>}
      {isLoading ? (
        <p className="text-sm text-[#6B6558]">Loading…</p>
      ) : (
        <>
          {tab === "coverage" && coverage && (
            <div>
              <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <StatBox label="Total documents" value={coverage.total_documents} />
                <StatBox label="Total chunks" value={coverage.total_chunks} />
                <StatBox label="Ever retrieved" value={coverage.documents_ever_retrieved} />
                <StatBox label="Never retrieved" value={coverage.documents_never_retrieved} accent="danger" />
              </div>
              <div className="mb-2 text-sm text-ink">
                Coverage rate:{" "}
                <span className="font-semibold">
                  {coverage.coverage_rate !== null ? `${(coverage.coverage_rate * 100).toFixed(1)}%` : "—"}
                </span>
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                <BreakdownBox title="By department" data={coverage.by_department} />
                <BreakdownBox title="By source type" data={coverage.by_source_type} />
                <BreakdownBox title="By file type" data={coverage.by_file_type} />
              </div>
            </div>
          )}

          {tab === "unanswered" && (
            <div className="space-y-4">
              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase text-[#6B6558]">Missing knowledge areas (keyword frequency)</h3>
                <div className="flex flex-wrap gap-1.5">
                  {missingAreas.map((a) => (
                    <span key={a.term} className="rounded bg-danger/10 px-2 py-1 text-xs text-danger">
                      {a.term} ({a.count})
                    </span>
                  ))}
                  {missingAreas.length === 0 && <span className="text-xs text-[#6B6558]">None — good sign.</span>}
                </div>
              </div>
              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase text-[#6B6558]">Unanswered questions</h3>
                {unanswered.length === 0 ? (
                  <p className="text-xs text-[#6B6558]">No unanswered questions recorded.</p>
                ) : (
                  <ul className="space-y-1.5 text-xs">
                    {unanswered.map((u) => (
                      <li key={u.message_id} className="rounded border border-rule bg-white px-3 py-2">
                        {u.question || "(unknown)"}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}

          {tab === "low_confidence" && (
            <div className="space-y-2">
              {lowConfidence.length === 0 ? (
                <p className="text-xs text-[#6B6558]">No low-confidence responses at the current threshold (0.3).</p>
              ) : (
                lowConfidence.map((r) => (
                  <div key={r.message_id} className="rounded border border-rule bg-white px-3 py-2 text-xs">
                    <div className="mb-1 flex justify-between">
                      <span className="font-mono text-[#6B6558]">confidence: {(r.max_confidence * 100).toFixed(1)}%</span>
                      <span className="text-[#6B6558]">{r.citation_count} citation(s)</span>
                    </div>
                    <p className="text-ink">{r.content}</p>
                  </div>
                ))
              )}
            </div>
          )}

          {tab === "never_retrieved" && (
            <table className="w-full text-left text-xs">
              <thead><tr className="text-[#6B6558]"><th className="py-1">Document</th><th className="py-1">Department</th></tr></thead>
              <tbody>
                {neverRetrieved.map((d) => (
                  <tr key={d.document_id} className="border-t border-rule/50">
                    <td className="py-1.5">{d.title}</td>
                    <td className="py-1.5 text-[#6B6558]">{d.department || "—"}</td>
                  </tr>
                ))}
                {neverRetrieved.length === 0 && <tr><td colSpan={2} className="py-4 text-center text-[#6B6558]">Every document has been retrieved at least once.</td></tr>}
              </tbody>
            </table>
          )}

          {tab === "stale" && (
            <table className="w-full text-left text-xs">
              <thead><tr className="text-[#6B6558]"><th className="py-1">Document</th><th className="py-1">Last updated</th><th className="py-1">Days old</th></tr></thead>
              <tbody>
                {stale.map((d) => (
                  <tr key={d.document_id} className="border-t border-rule/50">
                    <td className="py-1.5">{d.title}</td>
                    <td className="py-1.5 text-[#6B6558]">{d.last_updated ? new Date(d.last_updated).toLocaleDateString() : "—"}</td>
                    <td className="py-1.5 font-mono text-[#6B6558]">{d.days_since_update}</td>
                  </tr>
                ))}
                {stale.length === 0 && <tr><td colSpan={3} className="py-4 text-center text-[#6B6558]">Nothing older than 180 days.</td></tr>}
              </tbody>
            </table>
          )}

          {tab === "duplicates" && (
            <div>
              {duplicates.length === 0 ? (
                <p className="rounded border border-dashed border-rule bg-white/60 px-4 py-6 text-center text-xs text-[#6B6558]">
                  No duplicates found — expected, since exact-content duplicates are rejected at upload time.
                </p>
              ) : (
                duplicates.map((g) => (
                  <div key={g.content_hash} className="mb-2 rounded border border-danger/40 bg-danger/5 px-3 py-2 text-xs">
                    <div className="mb-1 font-medium text-danger">{g.count} documents share identical content</div>
                    {g.documents.map((d) => <div key={d.id}>{d.title}</div>)}
                  </div>
                ))
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function StatBox({ label, value, accent }: { label: string; value: number; accent?: "danger" }) {
  return (
    <div className="rounded border border-rule bg-white p-3">
      <div className={`font-display text-xl font-semibold ${accent === "danger" ? "text-danger" : "text-ink"}`}>{value}</div>
      <div className="text-[11px] text-[#6B6558]">{label}</div>
    </div>
  );
}

function BreakdownBox({ title, data }: { title: string; data: Record<string, number> }) {
  return (
    <div className="rounded border border-rule bg-white p-3">
      <div className="mb-1.5 text-xs font-semibold text-ink">{title}</div>
      {Object.entries(data).map(([k, v]) => (
        <div key={k} className="flex justify-between text-xs text-[#6B6558]">
          <span>{k}</span><span>{v}</span>
        </div>
      ))}
    </div>
  );
}
