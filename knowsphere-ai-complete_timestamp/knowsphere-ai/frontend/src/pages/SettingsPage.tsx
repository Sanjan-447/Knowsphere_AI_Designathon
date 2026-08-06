import { Link } from "react-router-dom";

export function SettingsPage() {
  return (
    <div className="mx-auto max-w-2xl px-10 py-10">
      <h1 className="font-display text-xl font-semibold text-ink">Settings</h1>
      <p className="mt-1 text-sm text-[#6B6558]">
        Organization-level configuration.
      </p>

      <div className="mt-6 space-y-3">
        <Link
          to="/settings/providers"
          className="flex items-center justify-between rounded border border-rule bg-white px-5 py-4 transition-colors hover:border-gold"
        >
          <div>
            <div className="font-medium text-ink">LLM provider management</div>
            <div className="text-sm text-[#6B6558]">
              Connect OpenAI, Anthropic, Gemini, and other providers; choose the default.
            </div>
          </div>
          <span className="text-gold">→</span>
        </Link>

        <Link
          to="/settings/langsmith"
          className="flex items-center justify-between rounded border border-rule bg-white px-5 py-4 transition-colors hover:border-gold"
        >
          <div>
            <div className="font-medium text-ink">LangSmith observability</div>
            <div className="text-sm text-[#6B6558]">
              Configure your LangSmith API key and enable trace collection for the RAG pipeline.
            </div>
          </div>
          <span className="text-gold">→</span>
        </Link>
      </div>
    </div>
  );
}
