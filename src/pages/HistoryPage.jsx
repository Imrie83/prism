import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  RefreshCw, Trash2, Mail, MailCheck,
  CheckSquare, Square, ExternalLink, AlertCircle, Inbox,
  Filter, CalendarClock,
} from "lucide-react";
import { api } from "../lib/api";
import SortHeader from "../components/SortHeader";
import PaginationFooter from "../components/PaginationFooter";
import { useScanStore } from "../stores/scanStore";
import { useSettingsStore } from "../stores/settingsStore";
import { useEmailStore } from "../stores/emailStore";

const PAGE_SIZE_OPTIONS = [15, 20, 30, 50, 100];

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
      {counts.high > 0 && <span style={{ fontSize: 10, fontWeight: 700, color: "#dc2626" }}>▲{counts.high}</span>}
      {counts.medium > 0 && <span style={{ fontSize: 10, fontWeight: 700, color: "#d97706" }}>●{counts.medium}</span>}
      {counts.low > 0 && <span style={{ fontSize: 10, fontWeight: 700, color: "#16a34a" }}>▼{counts.low}</span>}
    </span>
  );
}

// Sortable column header

export default function HistoryPage() {
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const historySettings = useSettingsStore();
  const { historyPerPage, setField } = historySettings;
  const perPage = historyPerPage;
  const setPerPage = (n) => setField("historyPerPage", n);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deletingUrl, setDeletingUrl] = useState(null);

  // Sort state — persisted
  const sortBy = historySettings.historySortBy;
  const sortDir = historySettings.historySortDir;
  const setSortBy = (v) => historySettings.setField("historySortBy", v);
  const setSortDir = (v) => historySettings.setField("historySortDir", v);

  // Filter state — persisted
  const filterEmail = historySettings.historyFilterEmail;
  const filterScoreMin = historySettings.historyFilterScoreMin;
  const filterScoreMax = historySettings.historyFilterScoreMax;
  const setFilterEmail = (v) => historySettings.setField("historyFilterEmail", v);
  const setFilterScoreMin = (v) => historySettings.setField("historyFilterScoreMin", v);
  const setFilterScoreMax = (v) => historySettings.setField("historyFilterScoreMax", v);
  const [showFilters, setShowFilters] = useState(false);

  const setActiveTab = useScanStore(s => s.setActiveTab);
  const finishShallow = useScanStore(s => s.finishShallow);
  const startShallow = useScanStore(s => s.startShallow);
  const openDrawerFor = useEmailStore(s => s.openDrawerFor);

  const load = useCallback(async (p = page) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getHistory(p, perPage, sortBy, sortDir, filterEmail, filterScoreMin, filterScoreMax);
      setRecords(data.records);
      setTotal(data.total);
    } catch (e) {
      setError("Could not load history: " + e.message);
    } finally {
      setLoading(false);
    }
  }, [page, perPage, sortBy, sortDir, filterEmail, filterScoreMin, filterScoreMax]);

  useEffect(() => { load(page); }, [page, perPage, sortBy, sortDir, filterEmail, filterScoreMin, filterScoreMax]);

  function handleSort(field) {
    if (sortBy === field) {
      setSortDir(sortDir === "desc" ? "asc" : "desc");
    } else {
      setSortBy(field);
      setSortDir("desc");
    }
    setPage(1);
  }

  function resetFilters() {
    setFilterEmail("all");
    setFilterScoreMin(0);
    setFilterScoreMax(100);
    setPage(1);
  }

  const hasActiveFilters = filterEmail !== "all" || filterScoreMin > 0 || filterScoreMax < 100;

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
    try {
      const full = await api.getHistoryEntry(record.url);
      const result = {
        url: full.url,
        score: full.score,
        title: full.title,
        summary: full.summary,
        totalIssues: full.total_issues,
        issueCounts: full.issue_counts,
        issues: full.issues || [],
        screenshot: full.screenshot_b64,
        scan_mode: full.scan_mode,
        _fromHistory: true,
      };
      const runId = startShallow(full.url);
      finishShallow(runId, result);
      if (full.email) {
        const emailPatch = { ...(useEmailStore.getState().emails[full.url] || {}) };
        if (full.email.recipient) emailPatch.recipientEmail = full.email.recipient;
        if (full.email.subject) emailPatch.subject = full.email.subject;
        if (full.email.html) emailPatch.htmlContent = full.email.html;
        if (full.email.sent_at) emailPatch.sentAt = full.email.sent_at;
        if (full.email.scheduled_at) emailPatch.scheduledAt = full.email.scheduled_at;
        emailPatch.status = full.email.status || (full.email.sent_at ? "sent" : full.email.html ? "ready" : undefined);
        useEmailStore.setState(s => ({ emails: { ...s.emails, [full.url]: emailPatch } }));
      }
      setActiveTab("results");
    } catch (e) {
      alert("Failed to load entry: " + e.message);
    }
  }

  const totalPages = Math.ceil(total / perPage);
  const COLS = "2fr 48px 90px 80px 130px 130px 80px 40px";

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1100, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "var(--ink1)" }}>
            Outreach History
          </h2>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--ink3)" }}>
            {total} site{total !== 1 ? "s" : ""}{hasActiveFilters ? " (filtered)" : ""} · click a row to reopen full results
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            className={`btn btn--sm ${hasActiveFilters ? "btn--primary" : "btn--ghost"}`}
            onClick={() => setShowFilters(f => !f)}
            style={{ position: "relative" }}>
            <Filter size={13} /> Filters
            {hasActiveFilters && (
              <span style={{
                position: "absolute", top: -4, right: -4, width: 8, height: 8,
                borderRadius: "50%", background: "var(--blue)",
              }} />
            )}
          </button>
          <label style={{ fontSize: 11, color: "var(--ink3)" }}>Show</label>
          <select
            value={perPage}
            onChange={e => { setPerPage(Number(e.target.value)); setPage(1); }}
            style={{
              fontSize: 11, padding: "3px 6px", borderRadius: "var(--radius)",
              border: "1px solid var(--border)", background: "var(--surface)",
              color: "var(--ink2)", cursor: "pointer",
            }}>
            {PAGE_SIZE_OPTIONS.map(n => <option key={n} value={n}>{n}</option>)}
          </select>
          <button className="btn btn--ghost btn--sm" onClick={() => load(page)} disabled={loading}>
            <RefreshCw size={13} className={loading ? "spin" : ""} /> Refresh
          </button>
        </div>
      </div>

      {/* Filter bar */}
      <AnimatePresence>
        {showFilters && (
          <motion.div
            initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }} style={{ overflow: "hidden", marginBottom: 12 }}>
            <div style={{
              display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap",
              padding: "12px 16px", background: "var(--surface)",
              border: "1px solid var(--border)", borderRadius: "var(--radius)",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 11, color: "var(--ink3)", fontWeight: 600 }}>EMAIL</span>
                <select
                  value={filterEmail}
                  onChange={e => { setFilterEmail(e.target.value); setPage(1); }}
                  style={{ fontSize: 11, padding: "3px 6px", borderRadius: 4, border: "1px solid var(--border)", background: "var(--bg3)", color: "var(--ink2)" }}>
                  <option value="all">All</option>
                  <option value="sent">Sent</option>
                  <option value="not_sent">Not sent</option>
                  <option value="got_response">Got response</option>
                </select>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 11, color: "var(--ink3)", fontWeight: 600 }}>SCORE</span>
                <input type="number" min={0} max={100} value={filterScoreMin}
                  onChange={e => { setFilterScoreMin(Number(e.target.value)); setPage(1); }}
                  style={{ width: 52, fontSize: 11, padding: "3px 6px", borderRadius: 4, border: "1px solid var(--border)", background: "var(--bg3)", color: "var(--ink2)" }} />
                <span style={{ fontSize: 11, color: "var(--ink3)" }}>-</span>
                <input type="number" min={0} max={100} value={filterScoreMax}
                  onChange={e => { setFilterScoreMax(Number(e.target.value)); setPage(1); }}
                  style={{ width: 52, fontSize: 11, padding: "3px 6px", borderRadius: 4, border: "1px solid var(--border)", background: "var(--bg3)", color: "var(--ink2)" }} />
              </div>
              {hasActiveFilters && (
                <button className="btn btn--ghost btn--sm" onClick={resetFilters} style={{ fontSize: 11 }}>
                  Clear filters
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

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
          <p style={{ margin: 0, fontSize: 14 }}>{hasActiveFilters ? "No records match your filters." : "No scans saved yet."}</p>
          {hasActiveFilters && <button className="btn btn--ghost btn--sm" onClick={resetFilters} style={{ marginTop: 10 }}>Clear filters</button>}
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
            display: "grid", gridTemplateColumns: COLS,
            gap: 0, padding: "9px 16px",
            borderBottom: "1px solid var(--border)",
            background: "var(--bg3)",
            fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}>
            <span style={{ color: "var(--ink3)" }}>URL</span>
            <SortHeader label="Score" field="score" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} style={{ justifyContent: "center" }} />
            <span style={{ color: "var(--ink3)" }}>Severity</span>
            <SortHeader label="Issues" field="total_issues" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} style={{ justifyContent: "center" }} />
            <SortHeader label="Scanned" field="scanned_at" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
            <SortHeader label="Email sent" field="email_sent" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
            <span style={{ color: "var(--ink3)" }}>Recipient</span>
            <span style={{ color: "var(--ink3)", textAlign: "center" }}>Reply</span>
          </div>

          {/* Rows */}
          <AnimatePresence initial={false}>
            {records.map((rec, i) => (
              <motion.div key={rec.url}
                initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 8 }} transition={{ delay: i * 0.02 }}
                onClick={() => handleRowClick(rec)}
                style={{
                  display: "grid", gridTemplateColumns: COLS,
                  gap: 0, padding: "10px 16px",
                  borderBottom: i < records.length - 1 ? "1px solid var(--border)" : "none",
                  cursor: "pointer", alignItems: "center", transition: "background 0.12s",
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

                <div style={{ display: "flex", justifyContent: "center" }}>
                  <ScorePip score={rec.score} />
                </div>
                <div><SevBadges counts={rec.issue_counts} /></div>
                <div style={{ fontSize: 12, color: "var(--ink2)", textAlign: "center" }}>{rec.total_issues ?? "—"}</div>
                <div style={{ fontSize: 12, color: "var(--ink2)" }}>{fmt(rec.scanned_at)}</div>
                <div style={{ fontSize: 12, color: (rec.email?.status === "scheduled" || rec.email?.sent_at) ? "var(--ink2)" : "var(--ink3)" }}>
                  {rec.email?.status === "scheduled" ? (
                    <span style={{ display: "flex", alignItems: "center", gap: 4, color: "#8b5cf6" }}>
                      <CalendarClock size={12} />
                      {fmt(rec.email.scheduled_at)}
                    </span>
                  ) : rec.email?.sent_at ? (
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
                <div style={{
                  fontSize: 11, color: "var(--ink3)", fontFamily: "var(--font-mono)",
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                }}>
                  {rec.email?.recipient || "—"}
                </div>
                <div style={{ display: "flex", justifyContent: "center", gap: 4 }}>
                  <button
                    onClick={e => handleToggleResponse(rec.url, e)}
                    style={{
                      background: "none", border: "none", cursor: "pointer",
                      color: rec.email?.got_response ? "var(--green)" : "var(--ink3)",
                      padding: 4, borderRadius: 4, display: "flex",
                    }}
                    title={rec.email?.got_response ? "Got response" : "No response yet"}>
                    {rec.email?.got_response ? <CheckSquare size={15} /> : <Square size={15} />}
                  </button>
                  <button
                    onClick={e => handleDelete(rec.url, e)}
                    disabled={deletingUrl === rec.url}
                    style={{
                      background: "none", border: "none", cursor: "pointer",
                      color: "var(--ink3)", padding: 4, borderRadius: 4, display: "flex",
                    }}
                    title="Delete record">
                    <Trash2 size={13} />
                  </button>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      <PaginationFooter
        page={page}
        totalPages={totalPages}
        total={total}
        perPage={perPage}
        onPage={setPage}
      />
    </div>
  );
}

