interface Props {
  label: string;
  value: string | number;
  sublabel?: string;
  accent?: "gold" | "teal" | "danger";
}

export function KpiCard({ label, value, sublabel, accent = "gold" }: Props) {
  const accentColor = { gold: "text-gold", teal: "text-teal", danger: "text-danger" }[accent];
  return (
    <div className="flex-1 rounded border border-rule bg-white p-4">
      <div className={`font-display text-2xl font-semibold text-ink`}>
        {value}
      </div>
      <div className="mt-0.5 text-xs text-[#6B6558]">{label}</div>
      {sublabel && <div className={`mt-1 text-[11px] ${accentColor}`}>{sublabel}</div>}
    </div>
  );
}
