import { useEffect, useState, type FormEvent } from "react";
import * as providersApi from "@/api/providers";
import type { ProviderConfig, SupportedProviderMeta } from "@/types";

export function ProviderManagementPage() {
  const [providers, setProviders] = useState<ProviderConfig[]>([]);
  const [supportedTypes, setSupportedTypes] = useState<Record<string, SupportedProviderMeta>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [providerType, setProviderType] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function loadAll() {
    setIsLoading(true);
    setError(null);
    try {
      const [providerList, types] = await Promise.all([
        providersApi.listProviders(),
        providersApi.listSupportedProviderTypes(),
      ]);
      setProviders(providerList);
      setSupportedTypes(types);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load providers.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  function flashBanner(message: string) {
    setBanner(message);
    setTimeout(() => setBanner(null), 3000);
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!displayName || !providerType) return;
    setSubmitting(true);
    setError(null);
    try {
      await providersApi.createProvider({
        display_name: displayName,
        provider_type: providerType,
        api_key: apiKey || undefined,
        base_url: baseUrl || undefined,
      });
      setDisplayName("");
      setProviderType("");
      setApiKey("");
      setBaseUrl("");
      setFormOpen(false);
      flashBanner("Provider added.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create provider.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleValidate(id: number) {
    try {
      const result = await providersApi.validateProvider(id);
      flashBanner(result.passed ? "Validation passed." : `Validation failed: ${result.errors.join(" ")}`);
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed.");
    }
  }

  async function handleSetDefault(id: number) {
    try {
      await providersApi.setDefaultProvider(id);
      flashBanner("Default provider updated.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to set default provider.");
    }
  }

  async function handleToggleActive(provider: ProviderConfig) {
    try {
      await providersApi.updateProvider(provider.id, { is_active: !provider.is_active });
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update provider.");
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this provider configuration? This cannot be undone.")) return;
    try {
      await providersApi.deleteProvider(id);
      flashBanner("Provider deleted.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete provider.");
    }
  }

  const selectedMeta = providerType ? supportedTypes[providerType] : undefined;

  return (
    <div className="mx-auto max-w-3xl px-10 py-10">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="font-display text-xl font-semibold text-ink">Provider settings</h1>
          <p className="mt-1 text-sm text-[#6B6558]">
            Manage LLM provider connections. Phase 1 stores configuration securely and runs format
            validation only — live connectivity checks and actual model calls arrive in a later phase.
          </p>
        </div>
        <button
          onClick={() => setFormOpen((v) => !v)}
          className="whitespace-nowrap rounded bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-ink-soft"
        >
          {formOpen ? "Cancel" : "Add provider"}
        </button>
      </div>

      {banner && (
        <div className="mb-4 rounded border border-teal/30 bg-teal/5 px-3 py-2 text-sm text-teal">{banner}</div>
      )}
      {error && (
        <div className="mb-4 rounded border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</div>
      )}

      {formOpen && (
        <form onSubmit={handleCreate} className="mb-6 rounded border border-dashed border-rule bg-white p-5">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-[#6B6558]">
                Display name
              </label>
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                required
                className="w-full rounded border border-rule px-3 py-2 text-sm focus:border-gold focus:outline-none"
                placeholder="e.g. Production Anthropic"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-[#6B6558]">
                Provider type
              </label>
              <select
                value={providerType}
                onChange={(e) => setProviderType(e.target.value)}
                required
                className="w-full rounded border border-rule bg-white px-3 py-2 text-sm focus:border-gold focus:outline-none"
              >
                <option value="">Select a provider…</option>
                {Object.entries(supportedTypes).map(([key, meta]) => (
                  <option key={key} value={key}>
                    {meta.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-[#6B6558]">
                API key {selectedMeta && !selectedMeta.key_prefix ? "(optional)" : ""}
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="w-full rounded border border-rule px-3 py-2 text-sm font-mono focus:border-gold focus:outline-none"
                placeholder={selectedMeta?.key_prefix ? `${selectedMeta.key_prefix}...` : "sk-..."}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-[#6B6558]">
                Base URL {selectedMeta?.requires_base_url ? "(required)" : "(optional)"}
              </label>
              <input
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                required={!!selectedMeta?.requires_base_url}
                className="w-full rounded border border-rule px-3 py-2 text-sm font-mono focus:border-gold focus:outline-none"
                placeholder="https://..."
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="mt-4 rounded bg-teal px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? "Saving…" : "Save provider"}
          </button>
        </form>
      )}

      {isLoading ? (
        <p className="text-sm text-[#6B6558]">Loading providers…</p>
      ) : providers.length === 0 ? (
        <p className="rounded border border-dashed border-rule bg-white/60 px-4 py-6 text-center text-sm text-[#6B6558]">
          No providers configured yet. Add one to get started.
        </p>
      ) : (
        <div className="space-y-3">
          {providers.map((p) => (
            <div key={p.id} className="rounded border border-rule bg-white p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-ink px-2 py-0.5 font-mono text-[11px] text-gold">
                      {supportedTypes[p.provider_type]?.label ?? p.provider_type}
                    </span>
                    <span className="font-medium text-ink">{p.display_name}</span>
                    {p.is_default && (
                      <span className="rounded bg-teal/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-teal">
                        Default
                      </span>
                    )}
                    {!p.is_active && (
                      <span className="rounded bg-danger/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-danger">
                        Disabled
                      </span>
                    )}
                  </div>
                  <div className="mt-1 font-mono text-xs text-[#6B6558]">
                    {p.api_key ?? "no key configured"} {p.base_url ? `· ${p.base_url}` : ""}
                  </div>
                  <div className="mt-1 text-xs text-[#6B6558]">
                    {p.last_validation_status === "passed" && "✓ Validation passed"}
                    {p.last_validation_status === "failed" && "✗ Validation failed"}
                    {!p.last_validation_status && "Not yet validated"}
                  </div>
                </div>
                <div className="flex flex-shrink-0 gap-2 text-xs">
                  <button
                    onClick={() => handleValidate(p.id)}
                    className="rounded border border-rule px-2.5 py-1.5 font-medium text-ink hover:bg-paper-dim"
                  >
                    Validate
                  </button>
                  {!p.is_default && p.is_active && (
                    <button
                      onClick={() => handleSetDefault(p.id)}
                      className="rounded border border-teal px-2.5 py-1.5 font-medium text-teal hover:bg-teal/5"
                    >
                      Set default
                    </button>
                  )}
                  <button
                    onClick={() => handleToggleActive(p)}
                    className="rounded border border-rule px-2.5 py-1.5 font-medium text-ink hover:bg-paper-dim"
                  >
                    {p.is_active ? "Disable" : "Enable"}
                  </button>
                  <button
                    onClick={() => handleDelete(p.id)}
                    className="rounded border border-danger/40 px-2.5 py-1.5 font-medium text-danger hover:bg-danger/5"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
