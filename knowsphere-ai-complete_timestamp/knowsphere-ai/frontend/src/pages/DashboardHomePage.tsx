import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from "recharts";
import { useAuth } from "@/context/AuthContext";
import * as analyticsApi from "@/api/analytics";
import type { OverviewStats, TrendPoint, ProviderUsageStat } from "@/types";
import { KpiCard } from "@/components/dashboard/KpiCard";

export function DashboardHomePage() {
  const { user } = useAuth();
  const canSeeAnalytics = user?.role === "admin" || user?.role === "manager";

  const [overview, setOverview] = useState<OverviewStats | null>(null);
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [providerUsage, setProviderUsage] = useState<ProviderUsageStat[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!canSeeAnalytics) {
      setIsLoading(false);
      return;
    }
    Promise.all([
      analyticsApi.getOverview(),
      analyticsApi.getTrends("day"),
      analyticsApi.getProviderUsageDistribution(),
    ])
      .then(([o, t, p]) => {
        setOverview(o);
        setTrends(t);
        setProviderUsage(p);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load dashboard."))
      .finally(() => setIsLoading(false));
  }, [canSeeAnalytics]);

  if (!canSeeAnalytics) {
    return (
      <div className="mx-auto max-w-2xl px-10 py-16 text-center">
        <div className="font-display text-2xl font-semibold text-ink">
          Welcome, {user?.display_name?.split(" ")[0]}
        </div>
        <p className="mx-auto mt-3 max-w-md text-sm text-[#6B6558]">
          You're signed in as <span className="font-medium text-ink">{user?.role}</span>. Head to{" "}
          <span className="font-medium text-ink">Ask Knowsphere</span> to start a conversation, or{" "}
          <span className="font-medium text-ink">Documents</span> to browse the knowledge library.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-10 py-10">
      <h1 className="font-display text-xl font-semibold text-ink">Enterprise Dashboard</h1>
      <p className="mt-1 text-sm text-[#6B6558]">Organization-wide activity, performance, and cost at a glance.</p>

      {error && <div className="mt-4 rounded border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</div>}
      {isLoading ? (
        <p className="mt-6 text-sm text-[#6B6558]">Loading…</p>
      ) : overview ? (
        <>
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <KpiCard label="Total users" value={overview.total_users} />
            <KpiCard label="Active users" value={overview.active_users} />
            <KpiCard label="Documents" value={overview.uploaded_documents} />
            <KpiCard label="Indexed chunks" value={overview.indexed_chunks} />
            <KpiCard label="Chat sessions" value={overview.chat_sessions} />
            <KpiCard label="Total queries" value={overview.total_queries} />
            <KpiCard label="Avg response time" value={`${overview.avg_response_time_ms}ms`} />
            <KpiCard label="Avg retrieval time" value={`${overview.avg_retrieval_time_ms}ms`} />
            <KpiCard label="Cache hit rate" value={`${(overview.cache_hit_rate * 100).toFixed(1)}%`} accent="teal" />
            <KpiCard label="Tokens consumed" value={overview.total_tokens_consumed.toLocaleString()} />
            <KpiCard
              label="Estimated API cost"
              value={`$${overview.estimated_api_cost_usd.toFixed(4)}`}
              sublabel="Illustrative rates — see docs"
            />
          </div>

          <div className="mt-8 grid gap-6 lg:grid-cols-2">
            <div className="rounded border border-rule bg-white p-4">
              <h2 className="mb-3 font-display text-sm font-semibold text-ink">Query volume (daily)</h2>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={trends}>
                  <CartesianGrid stroke="#EDE9DD" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v) => String(v).slice(5, 10)} />
                  <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                  <Tooltip />
                  <Line type="monotone" dataKey="query_count" stroke="#B8892B" strokeWidth={2} dot={false} name="Queries" />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="rounded border border-rule bg-white p-4">
              <h2 className="mb-3 font-display text-sm font-semibold text-ink">Provider usage</h2>
              {providerUsage.length === 0 ? (
                <p className="py-16 text-center text-xs text-[#6B6558]">No queries yet.</p>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={providerUsage}>
                    <CartesianGrid stroke="#EDE9DD" />
                    <XAxis dataKey="provider" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="query_count" fill="#2F5F58" name="Queries" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
