import type { Citation } from "@/types";

interface Props {
  citation: Citation;
  onClick?: () => void;
}

function citationTitle(c: Citation): string {
  const f = c.display_fields;
  switch (c.citation_type) {
    case "email":
      return f.subject || "Email";
    case "chat_export":
      return f.channel || "Chat export";
    case "share_link":
      return f.file_name || "Shared file";
    default:
      return f.document_name || "Document";
  }
}

function citationSubtitle(c: Citation): string {
  const f = c.display_fields;
  switch (c.citation_type) {
    case "email":
      return [f.sender, f.date].filter(Boolean).join(" · ") || "Email source";
    case "chat_export":
      return [f.sender, f.timestamp].filter(Boolean).join(" · ") || "Chat message";
    case "share_link":
      return f.source || "Shared link";
    default:
      return f.section ? `Section ${f.section}` : f.page ? `Page ${f.page}` : "Document";
  }
}

export function CitationCard({ citation, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-start gap-2 rounded border border-rule bg-white px-3 py-2 text-left text-xs transition-colors hover:border-gold"
    >
      <span className="mt-0.5 flex-shrink-0 rounded bg-ink px-1.5 py-0.5 font-mono text-[10px] text-gold">
        {citation.marker}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-medium text-ink">{citationTitle(citation)}</span>
        <span className="block truncate text-[#6B6558]">{citationSubtitle(citation)}</span>
      </span>
      {citation.confidence_score !== null && (
        <span className="flex-shrink-0 font-mono text-[10px] text-[#6B6558]">
          {(citation.confidence_score * 100).toFixed(0)}%
        </span>
      )}
    </button>
  );
}
