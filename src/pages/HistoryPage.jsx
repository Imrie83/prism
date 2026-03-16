import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  RefreshCw, Trash2, Mail, MailCheck, ChevronLeft, ChevronRight,
  CheckSquare, Square, ExternalLink, AlertCircle, Inbox
} from "lucide-react";
import { api } from "../lib/api";
import { useScanStore } from "../stores/scanStore";
import { useEmailStore } from "../stores/emailStore";

const PER_PAGE = 15;

function fmt(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

function shortUrl(url) {
  try {
    const u = new URL(url);
    return u.hostname + (u.pathname !== "/" ? u.pathname : "");
  } catch { return url; }
}

function ScorePip({ score }) {
  const col = score >= 75 ? "#16a34a" : score >= 45 ? "#d97706" : "#dc2626";
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      width: 36, height: 36, borderRadius: "50%",
      background: col + "18", border: `2px solid ${col}`,
      fontSize: 12, fontWeight: 800, color: col, flexShrink: 0,
    }}>
      {score}
    </span>
  );
}

function SevBadges({ counts }) {
  if (!counts) return <span style={{ color: "var(--ink3)", fontSize: 11 }}>—</span>;
  return (
    <span style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
      {counts.high   > 0 && <span style={{ fontSize: 10, fontWeight: 700, color: "#dc2626" }}>▲{counts.high}</span>}
      {counts.medium > 0 && <span style={{ fontSize: 10, fontWeight: 700, color: "#d97706" }}>●{counts.medium}</span>}
      {counts.low    > 0 && <span style={{ fontSize: 10, fontWeight: 700, color: "#16a34a" }}>▼{counts.low}</span>}
    </span>
  );
}

export default function HistoryPage() {
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deletingUrl, setDeletingUrl] = useState(null);

  const setActiveTab = useScanStore(s => s.setActiveTab);
  const finishShallow = useScanStore(s => s.finishShallow);
  const startShallow = useScanStore(s => s.startShallow);
  const openDrawerFor = useEmailStore(s => s.openDrawerFor);

  const load = useCallback(async (p = page) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getHistory(p, PER_PAGE);
      setRecords(data.records);
      setTotal(data.total);
    } catch (e) {
      setError("Could not load history: " + e.message);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => { load(page); }, [page]);

  async function handleToggleResponse(url, e) {
    e.stopPropagation();
    try {
      const res = await api.toggleResponse(url);
      setRecords(recs => recs.map(r =>
        r.url === url
          ? { ...r, email: { ...r.email, got_response: res.got_response } }
          : r
      ));
    } catch {}
  }

  async function handleDelete(url, e) {
    e.stopPropagation();
    if (!window.confirm(`Delete history for ${shortUrl(url)}?`)) return;
    setDeletingUrl(url);
    try {
      await api.deleteHistoryEntry(url);
      setRecords(recs => recs.filter(r => r.url !== url));
      setTotal(t => t - 1);
    } catch (e) {
      alert("Delete failed: " + e.message);
    } finally {
      setDeletingUrl(null);
    }
  }

  async function handleRowClick(record) {
    // Load full record (with screenshot) and rehydrate the scan store
    try {
      const full = await api.getHistoryEntry(record.url);

      // Reconstruct a result object matching what the scan engine produces
      const result = {
        url:          full.url,
        score:        full.score,
        title:        full.title,
        summary:      full.summary,
        totalIssues:  full.total_issues,
        issueCounts:  full.issue_counts,
        issues:       full.issues || [],
        screenshot:   full.screenshot_b64,
        scan_mode:    full.scan_mode,
        _fromHistory: true,
      };

      // Push into shallow history bank (history entries always reopen as shallow view)
      const runId = startShallow(full.url);
      finishShallow(runId, result);

      // Pre-fill email drawer state if email exists
      if (full.email) {
        const emailPatch = {
          ...(useEmailStore.getState().emails[full.url] || {}),
        };
        if (full.email.recipient) emailPatch.recipientEmail = full.email.recipient;
        if (full.email.subject)   emailPatch.subject        = full.email.subject;
        if (full.email.html)      emailPatch.htmlContent    = full.email.html;
        if (full.email.sent_at)   emailPatch.sentAt         = full.email.sent_at;
        // Derive status: sent > ready (has html) > undefined
        emailPatch.status = full.email.sent_at ? "sent" : full.email.html ? "ready" : undefined;
        useEmailStore.setState(s => ({
          emails: { ...s.emails, [full.url]: emailPatch },
        }));
      }

      setActiveTab("results");
    } catch (e) {
      alert("Failed to load entry: " + e.message);
    }
  }

  const totalPages = Math.ceil(total / PER_PAGE);

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1100, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "var(--ink1)" }}>
            Outreach History
          </h2>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--ink3)" }}>
            {total} site{total !== 1 ? "s" : ""} scanned · click a row to reopen full results
          </p>
        </div>
        <button className="btn btn--ghost btn--sm" onClick={() => load(page)} disabled={loading}>
          <RefreshCw size={13} className={loading ? "spin" : ""} /> Refresh
        </button>
      </div>

      {/* Error */}
      <AnimatePresence>
        {error && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="alert alert--error" style={{ marginBottom: 16 }}>
            <AlertCircle size={14} /> {error}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Empty state */}
      {!loading && records.length === 0 && !error && (
        <div style={{ textAlign: "center", padding: "80px 0", color: "var(--ink3)" }}>
          <Inbox size={40} style={{ marginBottom: 12, opacity: 0.4 }} />
          <p style={{ margin: 0, fontSize: 14 }}>No scans saved yet.</p>
          <p style={{ margin: "4px 0 0", fontSize: 12 }}>Run a Shallow or Batch scan to start building history.</p>
        </div>
      )}

      {/* Table */}
      {records.length > 0 && (
        <div style={{
          background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: "var(--radius)", overflow: "hidden",
        }}>
          {/* Table header */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "2fr 48px 90px 80px 130px 130px 80px 40px",
            gap: 0, padding: "9px 16px",
            borderBottom: "1px solid var(--border)",
            background: "var(--bg3)",
            fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
            textTransform: "uppercase", color: "var(--ink3)",
          }}>
            <span>URL</span>
            <span style={{ textAlign: "center" }}>Score</span>
            <span>Severity</span>
            <span style={{ textAlign: "center" }}>Issues</span>
            <span>Scanned</span>
            <span>Email sent</span>
            <span>Recipient</span>
            <span style={{ textAlign: "center" }}>Reply</span>
          </div>

          {/* Rows */}
          <AnimatePresence initial={false}>
            {records.map((rec, i) => (
              <motion.div key={rec.url}
                initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 8 }} transition={{ delay: i * 0.03 }}
                onClick={() => handleRowClick(rec)}
                style={{
                  display: "grid",
                  gridTemplateColumns: "2fr 48px 90px 80px 130px 130px 80px 40px",
                  gap: 0, padding: "10px 16px",
                  borderBottom: i < records.length - 1 ? "1px solid var(--border)" : "none",
                  cursor: "pointer", alignItems: "center",
                  transition: "background 0.12s",
                }}
                whileHover={{ background: "var(--surface2)" }}
              >
                {/* URL */}
                <div style={{ minWidth: 0 }}>
                  <div style={{
                    fontSize: 13, fontWeight: 600, color: "var(--ink1)",
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>
                    {rec.title || shortUrl(rec.url)}
                  </div>
                  <div style={{
                    fontSize: 11, color: "var(--ink3)", fontFamily: "var(--font-mono)",
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    display: "flex", alignItems: "center", gap: 4,
                  }}>
                    {shortUrl(rec.url)}
                    <a href={rec.url} target="_blank" rel="noreferrer"
                      onClick={e => e.stopPropagation()}
                      style={{ color: "var(--blue)", flexShrink: 0 }}>
                      <ExternalLink size={10} />
                    </a>
                  </div>
                </div>

                {/* Score */}
                <div style={{ display: "flex", justifyContent: "center" }}>
                  <ScorePip score={rec.score} />
                </div>

                {/* Severity badges */}
                <div><SevBadges counts={rec.issue_counts} /></div>

                {/* Total issues */}
                <div style={{ fontSize: 12, color: "var(--ink2)", textAlign: "center" }}>
                  {rec.total_issues ?? "—"}
                </div>

                {/* Scanned date */}
                <div style={{ fontSize: 12, color: "var(--ink2)" }}>{fmt(rec.scanned_at)}</div>

                {/* Email sent */}
                <div style={{ fontSize: 12, color: rec.email?.sent_at ? "var(--ink2)" : "var(--ink3)" }}>
                  {rec.email?.sent_at ? (
                    <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      <MailCheck size={12} style={{ color: "var(--green)" }} />
                      {fmt(rec.email.sent_at)}
                    </span>
                  ) : (
                    <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      <Mail size={12} style={{ opacity: 0.3 }} /> —
                    </span>
                  )}
                </div>

                {/* Recipient (truncated) */}
                <div style={{
                  fontSize: 11, color: "var(--ink3)", fontFamily: "var(--font-mono)",
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                }}>
                  {rec.email?.recipient || "—"}
                </div>

                {/* Response toggle */}
                <div style={{ display: "flex", justifyContent: "center", gap: 4 }}>
                  <button
                    onClick={e => handleToggleResponse(rec.url, e)}
                    style={{
                      background: "none", border: "none", cursor: "pointer",
                      color: rec.email?.got_response ? "var(--green)" : "var(--ink3)",
                      padding: 4, borderRadius: 4, display: "flex",
                    }}
                    title={rec.email?.got_response ? "Got response" : "No response yet"}
                  >
                    {rec.email?.got_response
                      ? <CheckSquare size={15} />
                      : <Square size={15} />
                    }
                  </button>
                  <button
                    onClick={e => handleDelete(rec.url, e)}
                    disabled={deletingUrl === rec.url}
                    style={{
                      background: "none", border: "none", cursor: "pointer",
                      color: "var(--ink3)", padding: 4, borderRadius: 4, display: "flex",
                    }}
                    title="Delete record"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "center",
          gap: 8, marginTop: 20,
        }}>
          <button className="btn btn--ghost btn--sm"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}>
            <ChevronLeft size={14} />
          </button>
          <span style={{ fontSize: 12, color: "var(--ink2)" }}>
            Page {page} of {totalPages}
          </span>
          <button className="btn btn--ghost btn--sm"
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}>
            <ChevronRight size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
