import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import * as analyticsApi from "@/api/analytics";
import type { TrendPoint, TopicCount, FrequentDocument, DepartmentUsage, FeedbackSummary, AnalyticsFilters } from "@/types";

const GRANULARITIES: Array<"day" | "week" | "month"> = ["day", "week", "month"];

export function AnalyticsPage() {
  const [granularity, setGranularity] = useState<"day" | "week" | "month">("day");
  const [filters, setFilters] = useState<AnalyticsFilters>({});
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [topics, setTopics] = useState<TopicCount[]>([]);
  const [docs, setDocs] = useState<FrequentDocument[]>([]);
  const [departments, setDepartments] = useState<DepartmentUsage[]>([]);
  const [feedback, setFeedback] = useState<FeedbackSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      const [t, tp, d, dept, fb] = await Promise.all([
        analyticsApi.getTrends(granularity, filters),
        analyticsApi.getTopics(15, filters),
        analyticsApi.getFrequentDocuments(10, filters),
        analyticsApi.getDepartmentUsage(filters),
        analyticsApi.getFeedbackSummary(filters),
      ]);
      setTrends(t);
      setTopics(tp);
      setDocs(d);
      setDepartments(dept);
      setFeedback(fb);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load analytics.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [granularity, filters]);

  async function handleExport(format: "csv" | "excel" | "pdf") {
    setExporting(format);
    try {
      await analyticsApi.downloadAnalyticsReport("usage", format);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed.");
    } finally {
      setExporting(null);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-10 py-10">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="font-display text-xl font-semibold text-ink">Analytics</h1>
          <p className="mt-1 text-sm text-[#6B6558]">Usage trends, topics, and effectiveness across the organization.</p>
        </div>
        <div className="flex gap-2">
          {(["csv", "excel", "pdf"] as const).map((fmt) => (
            <button
              key={fmt}
              onClick={() => handleExport(fmt)}
              disabled={exporting === fmt}
              className="rounded border border-rule px-3 py-1.5 text-xs font-medium text-ink hover:bg-paper-dim disabled:opacity-50"
            >
              {exporting === fmt ? "…" : `Export ${fmt.toUpperCase()}`}
            </button>
          ))}
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="flex rounded border border-rule bg-white">
          {GRANULARITIES.map((g) => (
            <button
              key={g}
              onClick={() => setGranularity(g)}
              className={`px-3 py-1.5 text-xs font-medium capitalize ${
                granularity === g ? "bg-ink text-paper" : "text-ink hover:bg-paper-dim"
              }`}
            >
              {g}
            </button>
          ))}
        </div>
        <input
          placeholder="Filter by department…"
          value={filters.department || ""}
          onChange={(e) => setFilters((f) => ({ ...f, department: e.target.value || undefined }))}
          className="rounded border border-rule px-3 py-1.5 text-xs focus:border-gold focus:outline-none"
        />
        <input
          placeholder="Filter by provider…"
          value={filters.provider || ""}
          onChange={(e) => setFilters((f) => ({ ...f, provider: e.target.value || undefined }))}
          className="rounded border border-rule px-3 py-1.5 text-xs focus:border-gold focus:outline-none"
        />
      </div>

      {error && <div className="mb-4 rounded border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</div>}

      {isLoading ? (
        <p className="text-sm text-[#6B6558]">Loading…</p>
      ) : (
        <div className="space-y-6">
          <div className="rounded border border-rule bg-white p-4">
            <h2 className="mb-3 font-display text-sm font-semibold text-ink">Activity trend</h2>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={trends}>
                <CartesianGrid stroke="#EDE9DD" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v) => String(v).slice(0, 10)} />
                <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                <Tooltip />
                <Line type="monotone" dataKey="query_count" stroke="#B8892B" strokeWidth={2} dot={false} name="Queries" />
                <Line type="monotone" dataKey="avg_response_time_ms" stroke="#2F5F58" strokeWidth={2} dot={false} name="Avg response (ms)" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded border border-rule bg-white p-4">
              <h2 className="mb-3 font-display text-sm font-semibold text-ink">Most asked topics</h2>
              <p className="mb-2 text-[11px] text-[#6B6558]">Keyword frequency, not semantic topic modeling.</p>
              {topics.length === 0 ? (
                <p className="text-xs text-[#6B6558]">No data yet.</p>
              ) : (
                <div className="space-y-1.5">
                  {topics.map((t) => (
                    <div key={t.term} className="flex items-center gap-2 text-xs">
                      <span className="w-24 flex-shrink-0 truncate font-mono text-ink">{t.term}</span>
                      <div className="h-2 flex-1 overflow-hidden rounded bg-paper-dim">
                        <div className="h-full bg-gold" style={{ width: `${(t.count / topics[0].count) * 100}%` }} />
                      </div>
                      <span className="w-6 text-right text-[#6B6558]">{t.count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded border border-rule bg-white p-4">
              <h2 className="mb-3 font-display text-sm font-semibold text-ink">Frequently accessed documents</h2>
              {docs.length === 0 ? (
                <p className="text-xs text-[#6B6558]">No citations yet.</p>
              ) : (
                <table className="w-full text-left text-xs">
                  <tbody>
                    {docs.map((d) => (
                      <tr key={d.document_id} className="border-t border-rule/50">
                        <td className="truncate py-1.5 pr-2">{d.title}</td>
                        <td className="py-1.5 text-right font-mono text-[#6B6558]">{d.citation_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded border border-rule bg-white p-4">
              <h2 className="mb-3 font-display text-sm font-semibold text-ink">Department usage</h2>
              {departments.length === 0 ? (
                <p className="text-xs text-[#6B6558]">No data yet.</p>
              ) : (
                <div className="space-y-1.5">
                  {departments.map((d) => (
                    <div key={d.department} className="flex justify-between text-xs">
                      <span className="text-ink">{d.department}</span>
                      <span className="text-[#6B6558]">{d.citation_count} citations</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded border border-rule bg-white p-4">
              <h2 className="mb-3 font-display text-sm font-semibold text-ink">Feedback effectiveness</h2>
              {feedback && feedback.total_feedback > 0 ? (
                <div className="text-xs">
                  <div className="mb-2 flex gap-4">
                    <span className="text-teal">👍 {feedback.helpful}</span>
                    <span className="text-danger">👎 {feedback.not_helpful}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded bg-danger/20">
                    <div className="h-full bg-teal" style={{ width: `${(feedback.helpful_rate || 0) * 100}%` }} />
                  </div>
                  <p className="mt-1.5 text-[#6B6558]">{((feedback.helpful_rate || 0) * 100).toFixed(0)}% helpful</p>
                </div>
              ) : (
                <p className="text-xs text-[#6B6558]">No feedback submitted yet.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
