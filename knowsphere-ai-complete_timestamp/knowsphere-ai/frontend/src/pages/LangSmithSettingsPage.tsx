import { useEffect, useState } from "react";
import * as monitoringApi from "@/api/monitoring";
import type { LangSmithConfig } from "@/types";

export function LangSmithSettingsPage() {
  const [config, setConfig] = useState<LangSmithConfig | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [projectName, setProjectName] = useState("");
  const [tracingEnabled, setTracingEnabled] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setIsLoading(true);
    try {
      const c = await monitoringApi.getLangSmithConfig();
      setConfig(c);
      setProjectName(c.project_name);
      setTracingEnabled(c.tracing_enabled);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load configuration.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = { project_name: projectName, tracing_enabled: tracingEnabled };
      if (apiKey) payload.api_key = apiKey;
      const updated = await monitoringApi.updateLangSmithConfig(payload);
      setConfig(updated);
      setApiKey("");
      setBanner("Settings saved.");
      setTimeout(() => setBanner(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save.");
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    setError(null);
    try {
      const result = await monitoringApi.testLangSmithConnection();
      setConfig(result.data);
      setBanner(result.message);
      setTimeout(() => setBanner(null), 5000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test failed.");
    } finally {
      setTesting(false);
    }
  }

  if (isLoading) return <div className="mx-auto max-w-xl px-10 py-10 text-sm text-[#6B6558]">Loading…</div>;

  return (
    <div className="mx-auto max-w-xl px-10 py-10">
      <h1 className="font-display text-xl font-semibold text-ink">LangSmith observability</h1>
      <p className="mt-1 text-sm text-[#6B6558]">
        Trace the full RAG pipeline (retrieval, reranking, prompting, generation, citations) in LangSmith.
      </p>

      {banner && <div className="mt-4 rounded border border-teal/30 bg-teal/5 px-3 py-2 text-sm text-teal">{banner}</div>}
      {error && <div className="mt-4 rounded border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</div>}

      <div className="mt-6 space-y-4">
        <div>
          <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-[#6B6558]">API key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={config?.has_api_key ? "•••••••• (set — enter a new key to replace)" : "lsv2_..."}
            className="w-full rounded border border-rule px-3 py-2 text-sm font-mono focus:border-gold focus:outline-none"
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-[#6B6558]">Project name</label>
          <input
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            className="w-full rounded border border-rule px-3 py-2 text-sm focus:border-gold focus:outline-none"
          />
        </div>

        <div className="flex items-center justify-between rounded border border-rule px-4 py-3">
          <div>
            <div className="text-sm font-medium text-ink">Enable tracing</div>
            <div className="text-xs text-[#6B6558]">Requires an API key. Covers non-streaming chat fully, streaming as a single summary trace.</div>
          </div>
          <input type="checkbox" checked={tracingEnabled} onChange={(e) => setTracingEnabled(e.target.checked)} />
        </div>

        {config?.last_test_status && (
          <div className="text-xs text-[#6B6558]">
            Last connection test: <span className={config.last_test_status === "passed" ? "text-teal" : "text-danger"}>{config.last_test_status}</span>
            {config.last_test_message && ` — ${config.last_test_message}`}
          </div>
        )}

        <div className="flex gap-2">
          <button onClick={handleSave} disabled={saving} className="rounded bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-ink-soft disabled:opacity-50">
            {saving ? "Saving…" : "Save"}
          </button>
          <button onClick={handleTest} disabled={testing || !config?.has_api_key} className="rounded border border-rule px-4 py-2 text-sm font-medium text-ink hover:bg-paper-dim disabled:opacity-50">
            {testing ? "Testing…" : "Test connection"}
          </button>
        </div>
      </div>
    </div>
  );
}
