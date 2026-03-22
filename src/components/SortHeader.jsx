import { ChevronDown, ChevronUp } from "lucide-react";

/**
 * Reusable sortable column header.
 * Renders an inline clickable label with up/down chevron indicating sort state.
 */
export default function SortHeader({ label, field, sortBy, sortDir, onSort, style = {} }) {
  const active = sortBy === field;
  return (
    <span
      onClick={() => onSort(field)}
      style={{
        cursor: "pointer",
        userSelect: "none",
        display: "inline-flex",
        alignItems: "center",
        gap: 3,
        color: active ? "var(--blue)" : "var(--ink3)",
        ...style,
      }}
    >
      {label}
      {active
        ? sortDir === "desc"
          ? <ChevronDown size={10} />
          : <ChevronUp size={10} />
        : <ChevronDown size={10} style={{ opacity: 0.3 }} />}
    </span>
  );
}
