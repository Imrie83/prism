import { ChevronLeft, ChevronRight } from "lucide-react";

/**
 * Reusable pagination footer — prev/next arrows + page number buttons.
 * Used in HistoryPage and DiscoverPage.
 *
 * Props:
 *   page        — current page (1-based)
 *   totalPages  — total number of pages
 *   total       — total record count (for "X–Y of Z" display)
 *   perPage     — records per page (0 = all)
 *   onPage      — callback(newPage)
 */
export default function PaginationFooter({ page, totalPages, total, perPage, onPage }) {
  if (totalPages <= 1) return null;

  const from = perPage === 0 ? 1      : (page - 1) * perPage + 1;
  const to   = perPage === 0 ? total  : Math.min(page * perPage, total);

  // Build page number array (max 7 visible, windowed around current)
  const pageNumbers = Array.from({ length: Math.min(totalPages, 7) }, (_, idx) => {
    if (totalPages <= 7)          return idx + 1;
    if (page <= 4)                return idx + 1;
    if (page >= totalPages - 3)   return totalPages - 6 + idx;
    return page - 3 + idx;
  });

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "10px 16px",
      borderTop: "1px solid var(--border)",
      background: "var(--bg3)",
    }}>
      <span style={{ fontSize: 11, color: "var(--ink3)" }}>
        {perPage === 0 ? `All ${total}` : `${from}–${to} of ${total}`}
      </span>
      <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
        <button
          className="btn btn--ghost btn--sm"
          onClick={() => onPage(Math.max(1, page - 1))}
          disabled={page === 1}
        >
          <ChevronLeft size={13} />
        </button>
        {pageNumbers.map(p => (
          <button
            key={p}
            onClick={() => onPage(p)}
            style={{
              minWidth: 28,
              height: 28,
              borderRadius: 6,
              border: `1px solid ${p === page ? "var(--blue-line)" : "var(--border)"}`,
              background: p === page ? "var(--blue-glow)" : "transparent",
              color: p === page ? "var(--blue)" : "var(--ink3)",
              fontSize: 12,
              cursor: "pointer",
              fontWeight: p === page ? 700 : 400,
            }}
          >
            {p}
          </button>
        ))}
        <button
          className="btn btn--ghost btn--sm"
          onClick={() => onPage(Math.min(totalPages, page + 1))}
          disabled={page === totalPages}
        >
          <ChevronRight size={13} />
        </button>
      </div>
    </div>
  );
}
