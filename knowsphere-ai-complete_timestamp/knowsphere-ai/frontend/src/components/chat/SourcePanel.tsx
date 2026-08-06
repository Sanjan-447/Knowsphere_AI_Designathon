import type { Citation } from "@/types";

interface Props {
  citation: Citation | null;
  onClose: () => void;
}

export function SourcePanel({ citation, onClose }: Props) {
  const isOpen = !!citation;

  return (
    <>
      <div
        className={`fixed inset-0 z-10 bg-ink/25 transition-opacity ${isOpen ? "opacity-100" : "pointer-events-none opacity-0"}`}
        onClick={onClose}
      />
      <div
        className={`fixed right-0 top-0 z-20 h-full w-[380px] transform border-l border-rule bg-paper shadow-xl transition-transform ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {citation && (
          <div className="flex h-full flex-col">
            <div className="flex items-start justify-between border-b border-rule px-6 py-5">
              <div>
                <span className="rounded bg-ink px-1.5 py-0.5 font-mono text-[10px] text-gold">
                  [{citation.marker}]
                </span>
                <div className="mt-1 font-display text-base font-semibold text-ink capitalize">
                  {citation.citation_type.replace("_", " ")}
                </div>
              </div>
              <button onClick={onClose} className="text-lg text-[#6B6558] hover:text-ink">✕</button>
            </div>
            <div className="flex-1 overflow-y-auto px-6 py-5 text-sm">
              <dl className="mb-5 space-y-1.5 text-xs">
                {Object.entries(citation.display_fields).map(([key, value]) =>
                  value ? (
                    <div key={key} className="flex justify-between gap-3">
                      <dt className="capitalize text-[#6B6558]">{key.replace("_", " ")}</dt>
                      <dd className="truncate text-right text-ink">{String(value)}</dd>
                    </div>
                  ) : null
                )}
                {citation.confidence_score !== null && (
                  <div className="flex justify-between gap-3">
                    <dt className="text-[#6B6558]">Similarity</dt>
                    <dd className="text-ink">{(citation.confidence_score * 100).toFixed(1)}%</dd>
                  </div>
                )}
              </dl>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[#6B6558]">Excerpt</h3>
              <p className="whitespace-pre-line rounded border border-rule bg-white p-3 text-xs leading-relaxed text-[#3a3a3a]">
                {citation.snippet || "No excerpt available."}
              </p>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
