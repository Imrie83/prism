/**
 * Pill badge showing a prospect status.
 * Used in DiscoverPage — extracted for potential reuse in HistoryPage.
 */
const STATUS_META = {
  new: { label: "New", color: "var(--blue)", bg: "var(--blue-glow)" },
  pending: { label: "Unscanned",color: "var(--ink3)", bg: "var(--surface)" },
  queued: { label: "Queued", color: "#f59e0b", bg: "rgba(245,158,11,0.1)" },
  scanning: { label: "Scanning", color: "var(--blue)", bg: "var(--blue-glow)" },
  scanned: { label: "Scanned", color: "var(--green)", bg: "rgba(52,211,153,0.1)" },
  emailed: { label: "Emailed", color: "var(--accent)", bg: "rgba(251,191,36,0.1)" },
  scheduled: { label: "Scheduled", color: "#8b5cf6", bg: "rgba(139,92,246,0.1)" },
  skipped: { label: "Skipped", color: "var(--ink3)", bg: "var(--surface)" },
  bounced: { label: "Bounced", color: "#ef4444", bg: "rgba(239,68,68,0.1)" },
  cant_deliver: { label: "Can't Deliver", color: "#dc2626", bg: "rgba(220,38,38,0.15)" },
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
