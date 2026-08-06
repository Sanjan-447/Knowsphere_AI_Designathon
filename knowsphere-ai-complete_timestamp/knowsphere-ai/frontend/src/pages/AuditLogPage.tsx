import { useEffect, useState } from "react";
import * as auditApi from "@/api/audit";
import type { AuditLogEntry } from "@/types";
import { downloadAuditExport } from "@/api/analytics";

export function AuditLogPage() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [actionTypes, setActionTypes] = useState<string[]>([]);
  const [actionFilter, setActionFilter] = useState("");
  const [emailFilter, setEmailFilter] = useState("");
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);
  const pageSize = 25;

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      const data = await auditApi.listAuditLogs({
        action: actionFilter || undefined, actor_email: emailFilter || undefined,
        page, page_size: pageSize,
      });
      setLogs(data.logs);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load audit logs.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    auditApi.listActionTypes().then(setActionTypes).catch(() => {});
  }, []);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actionFilter, emailFilter, page]);

  async function handleExport(fmt: "csv" | "excel" | "pdf") {
    setExporting(fmt);
    try {
      await downloadAuditExport(fmt);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed.");
    } finally {
      setExporting(null);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="mx-auto max-w-5xl px-10 py-10">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="font-display text-xl font-semibold text-ink">Audit log</h1>
          <p className="mt-1 text-sm text-[#6B6558]">Immutable record of every auditable action — read and export only.</p>
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

      <div className="mb-4 flex flex-wrap gap-2">
        <select
          value={actionFilter}
          onChange={(e) => { setActionFilter(e.target.value); setPage(1); }}
          className="rounded border border-rule bg-white px-3 py-1.5 text-xs focus:border-gold focus:outline-none"
        >
          <option value="">All actions</option>
          {actionTypes.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
        <input
          placeholder="Filter by email…"
          value={emailFilter}
          onChange={(e) => { setEmailFilter(e.target.value); setPage(1); }}
          className="rounded border border-rule px-3 py-1.5 text-xs focus:border-gold focus:outline-none"
        />
      </div>

      {error && <div className="mb-4 rounded border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</div>}

      <div className="overflow-x-auto rounded border border-rule bg-white">
        <table className="w-full text-left text-xs">
          <thead className="bg-paper-dim text-[#6B6558]">
            <tr>
              <th className="px-3 py-2">Time</th>
              <th className="px-3 py-2">Actor</th>
              <th className="px-3 py-2">Action</th>
              <th className="px-3 py-2">Resource</th>
              <th className="px-3 py-2">Details</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={5} className="px-3 py-6 text-center text-[#6B6558]">Loading…</td></tr>
            ) : logs.length === 0 ? (
              <tr><td colSpan={5} className="px-3 py-6 text-center text-[#6B6558]">No matching audit entries.</td></tr>
            ) : (
              logs.map((log) => (
                <tr key={log.id} className="border-t border-rule/50 align-top">
                  <td className="whitespace-nowrap px-3 py-2 text-[#6B6558]">{new Date(log.created_at).toLocaleString()}</td>
                  <td className="px-3 py-2">{log.actor_email || "—"} <span className="text-[#6B6558]">({log.actor_role || "n/a"})</span></td>
                  <td className="px-3 py-2"><span className="rounded bg-ink px-1.5 py-0.5 font-mono text-[10px] text-gold">{log.action}</span></td>
                  <td className="px-3 py-2 text-[#6B6558]">{log.resource_type ? `${log.resource_type}#${log.resource_id}` : "—"}</td>
                  <td className="max-w-xs truncate px-3 py-2 text-[#6B6558]" title={JSON.stringify(log.details)}>
                    {JSON.stringify(log.details)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex items-center justify-between text-xs text-[#6B6558]">
        <span>{total} total entries</span>
        <div className="flex gap-2">
          <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="rounded border border-rule px-2 py-1 disabled:opacity-40">Prev</button>
          <span>Page {page} of {totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} className="rounded border border-rule px-2 py-1 disabled:opacity-40">Next</button>
        </div>
      </div>
    </div>
  );
}
