import { useEffect, useState } from "react";
import * as monitoringApi from "@/api/monitoring";
import type { SystemStatus, ProviderMonitoringStat } from "@/types";
import { HealthBadge } from "@/components/dashboard/HealthBadge";

export function SystemMonitoringPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [providers, setProviders] = useState<ProviderMonitoringStat[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  async function load() {
    setError(null);
    try {
      const [s, p] = await Promise.all([monitoringApi.getSystemStatus(), monitoringApi.getProviderMonitoring()]);
      setStatus(s);
      setProviders(p);
      setLastChecked(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load system status.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-10 py-10">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="font-display text-xl font-semibold text-ink">System monitoring</h1>
          <p className="mt-1 text-sm text-[#6B6558]">
            Live infrastructure health — not simulated. {lastChecked && `Last checked ${lastChecked.toLocaleTimeString()}.`}
          </p>
        </div>
        <button onClick={load} className="rounded border border-rule px-3 py-1.5 text-xs font-medium text-ink hover:bg-paper-dim">
          Refresh
        </button>
      </div>

      {error && <div className="mb-4 rounded border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</div>}

      {isLoading ? (
        <p className="text-sm text-[#6B6558]">Checking…</p>
      ) : status ? (
        <>
          <div className="mb-6 rounded border border-rule bg-white p-4">
            <div className="flex items-center justify-between">
              <span className="font-display text-sm font-semibold text-ink">Overall status</span>
              <HealthBadge status={status.overall_status} />
            </div>
          </div>

          <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <ServiceCard title="PostgreSQL" result={status.postgresql} />
            <ServiceCard title="pgvector" result={status.pgvector} />
            <ServiceCard title="Redis" result={status.redis} />
            <ServiceCard title="Celery" result={status.celery} />
          </div>

          <div className="mb-6 grid gap-4 sm:grid-cols-2">
            <div className="rounded border border-rule bg-white p-4">
              <h2 className="mb-2 font-display text-sm font-semibold text-ink">Storage</h2>
              <dl className="space-y-1 text-xs">
                <Row label="Disk used" value={`${status.storage.disk_used_gb} GB / ${status.storage.disk_total_gb} GB`} />
                <Row label="Disk free" value={`${status.storage.disk_free_gb} GB`} />
                <Row label="Uploads folder" value={`${status.storage.upload_dir_size_mb} MB`} />
              </dl>
              <div className="mt-2 h-2 overflow-hidden rounded bg-paper-dim">
                <div className="h-full bg-gold" style={{ width: `${status.storage.disk_used_percent}%` }} />
              </div>
            </div>
            <div className="rounded border border-rule bg-white p-4">
              <h2 className="mb-2 font-display text-sm font-semibold text-ink">Resources</h2>
              <dl className="space-y-1 text-xs">
                <Row label="CPU" value={`${status.resources.cpu_percent}%`} />
                <Row label="Memory" value={`${status.resources.memory_used_mb} MB / ${status.resources.memory_total_mb} MB`} />
              </dl>
              <div className="mt-2 h-2 overflow-hidden rounded bg-paper-dim">
                <div className="h-full bg-teal" style={{ width: `${status.resources.memory_percent}%` }} />
              </div>
            </div>
          </div>
        </>
      ) : null}

      <h2 className="mb-3 font-display text-sm font-semibold text-ink">Provider monitoring</h2>
      <div className="overflow-x-auto rounded border border-rule bg-white">
        <table className="w-full text-left text-xs">
          <thead className="bg-paper-dim text-[#6B6558]">
            <tr>
              <th className="px-3 py-2">Provider</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Queries</th>
              <th className="px-3 py-2">Success rate</th>
              <th className="px-3 py-2">Avg response</th>
              <th className="px-3 py-2">Tokens</th>
              <th className="px-3 py-2">Est. cost</th>
              <th className="px-3 py-2">Last used</th>
            </tr>
          </thead>
          <tbody>
            {providers.map((p) => (
              <tr key={p.provider_config_id} className="border-t border-rule/50">
                <td className="px-3 py-2">
                  {p.display_name}
                  {p.is_default && <span className="ml-1.5 rounded bg-teal/10 px-1.5 py-0.5 text-[10px] text-teal">default</span>}
                </td>
                <td className="px-3 py-2">
                  <HealthBadge status={p.is_active ? "healthy" : "unhealthy"} label={p.is_active ? "active" : "disabled"} />
                </td>
                <td className="px-3 py-2 font-mono">{p.query_count}</td>
                <td className="px-3 py-2 font-mono">{p.success_rate !== null ? `${(p.success_rate * 100).toFixed(0)}%` : "—"}</td>
                <td className="px-3 py-2 font-mono">{p.avg_response_time_ms}ms</td>
                <td className="px-3 py-2 font-mono">{p.total_tokens.toLocaleString()}</td>
                <td className="px-3 py-2 font-mono">${p.estimated_cost_usd.toFixed(4)}</td>
                <td className="px-3 py-2 text-[#6B6558]">{p.last_used ? new Date(p.last_used).toLocaleString() : "never"}</td>
              </tr>
            ))}
            {providers.length === 0 && (
              <tr><td colSpan={8} className="px-3 py-6 text-center text-[#6B6558]">No providers configured yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ServiceCard({ title, result }: { title: string; result: { status: string; message: string } }) {
  return (
    <div className="rounded border border-rule bg-white p-3">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-xs font-semibold text-ink">{title}</span>
        <HealthBadge status={result.status} />
      </div>
      <p className="text-[11px] text-[#6B6558]">{result.message}</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-[#6B6558]">{label}</span>
      <span className="font-mono text-ink">{value}</span>
    </div>
  );
}
