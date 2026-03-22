/**
 * Pill badge showing a prospect status.
 * Used in DiscoverPage — extracted for potential reuse in HistoryPage.
 */
const STATUS_META = {
  new:      { label: "New",      color: "var(--ink3)",   bg: "var(--surface)" },
  queued:   { label: "Queued",   color: "var(--blue)",   bg: "var(--blue-glow)" },
  scanning: { label: "Scanning", color: "var(--blue)",   bg: "var(--blue-glow)" },
  scanned:  { label: "Scanned",  color: "var(--green)",  bg: "rgba(52,211,153,0.1)" },
  emailed:  { label: "Emailed",  color: "var(--accent)", bg: "rgba(251,191,36,0.1)" },
  skipped:  { label: "Skipped",  color: "var(--ink3)",   bg: "var(--surface)" },
};

export default function StatusBadge({ status }) {
  const m = STATUS_META[status] || STATUS_META.new;
  return (
    <span style={{
      fontSize: 10,
      fontWeight: 700,
      padding: "2px 7px",
      borderRadius: 99,
      color: m.color,
      background: m.bg,
      border: `1px solid ${m.color}30`,
      fontFamily: "var(--font-mono)",
      whiteSpace: "nowrap",
    }}>
      {m.label}
    </span>
  );
}
