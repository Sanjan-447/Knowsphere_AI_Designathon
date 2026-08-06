interface Props {
  status: string;
  label?: string;
}

export function HealthBadge({ status, label }: Props) {
  const isHealthy = status === "healthy" || status === "passed" || status === "clean";
  const isUnknown = status === null || status === undefined || status === "not_configured";
  const colorClass = isUnknown
    ? "bg-paper-dim text-[#6B6558]"
    : isHealthy
      ? "bg-teal/10 text-teal"
      : "bg-danger/10 text-danger";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded px-2 py-1 text-xs font-medium ${colorClass}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${isUnknown ? "bg-[#6B6558]" : isHealthy ? "bg-teal" : "bg-danger"}`} />
      {label || status}
    </span>
  );
}
