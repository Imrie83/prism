import { useEffect, useCallback, useRef } from "react";
import { useDiscoverStore } from "../stores/discoverStore";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search, MapPin, ScanLine, ExternalLink, Trash2,
  RefreshCw, AlertCircle, Inbox,
  Globe, Star, CheckCircle, Filter, CheckSquare, Square,
  Bookmark, X, Ban, MessageSquare
} from "lucide-react";
import { api } from "../lib/api";
import SortHeader from "../components/SortHeader";
import StatusBadge from "../components/StatusBadge";
import PaginationFooter from "../components/PaginationFooter";
import { useAISettings } from "../hooks/useAISettings";
import { useSettingsStore } from "../stores/settingsStore";
import { useEmailStore } from "../stores/emailStore";
import { useScanStore } from "../stores/scanStore";


function RatingStars({ rating }) {
  if (!rating) return <span style={{ color: "var(--ink3)", fontSize: 11 }}>—</span>;
  return (
    <span style={{ display: "flex", alignItems: "center", gap: 3, fontSize: 11 }}>
      <Star size={10} style={{ color: "#f59e0b", fill: "#f59e0b" }} />
      <span style={{ color: "var(--ink2)", fontWeight: 600 }}>{rating}</span>
    </span>
  );
}


const LIMIT_OPTIONS = [
  { label: "60", value: 60 },
  { label: "120", value: 120 },
  { label: "200", value: 200 },
  { label: "All", value: 0 },
];

const PER_PAGE_OPTIONS = [10, 25, 50, 100];

export default function DiscoverPage() {
  const settings = useSettingsStore();
  const emailStore = useEmailStore();
  const scanStore = useScanStore();
  const { getScanSettings, getEmailSettings } = useAISettings();

  // All transient state lives in discoverStore so it survives tab switches
  const ds = useDiscoverStore();
  const keywords = ds.keywords;
  const location = ds.location;
  const limit = ds.limit;
  const searching = ds.searching;
  const searchError = ds.searchError;
  const searchStats = ds.searchStats;
  const searchProgress = ds.searchProgress;
  const sessions = ds.sessions;
  const activeSession = ds.activeSession;
  const records = ds.records;
  const loading = ds.loading;
  const page = ds.page;
  const showFilters = ds.showFilters;
  const showSuggestions = ds.showSuggestions;

  const setKeywords = (v) => ds.setField("keywords", v);
  const setLocation = (v) => ds.setField("location", v);
  const setLimit = (v) => ds.setField("limit", v);
  const setSearching = (v) => ds.setField("searching", v);
  const setSearchError = (v) => ds.setField("searchError", v);
  const setSearchStats = (v) => ds.setField("searchStats", v);
  const setSearchProgress = (v) => ds.setField("searchProgress", v);
  const setSessions = (v) => ds.setField("sessions", v);
  const setActiveSession = (v) => ds.setField("activeSession", v);
  const setRecords = (v) => ds.setField("records", typeof v === "function" ? v(records) : v);
  const setLoading = (v) => ds.setField("loading", v);
  const setPage = (v) => ds.setField("page", typeof v === "function" ? v(page) : v);
  const setShowFilters = (v) => ds.setField("showFilters", typeof v === "function" ? v(showFilters) : v);
  const setShowSuggestions = (v) => ds.setField("showSuggestions", v);

  // Selected is stored as array in store, expose as Set for compatibility
  const selected = new Set(ds.selected);
  const setSelected = (setOrFn) => {
    if (typeof setOrFn === "function") {
      const next = setOrFn(new Set(ds.selected));
      ds.setField("selected", [...next]);
    } else {
      ds.setField("selected", [...setOrFn]);
    }
  };

  // Sort / filter / pagination — persisted via settingsStore
  const sortBy = settings.discoverSortBy;
  const sortDir = settings.discoverSortDir;
  const filterStatus = settings.discoverFilterStatus;
  const filterHasEmail = settings.discoverFilterHasEmail;
  const discoverSearch = settings.discoverSearch;
  const perPage = settings.discoverPerPage;
  const setSortBy = (v) => settings.setField("discoverSortBy", v);
  const setSortDir = (v) => settings.setField("discoverSortDir", v);
  const setFilterStatus = (v) => settings.setField("discoverFilterStatus", v);
  const setFilterHasEmail = (v) => settings.setField("discoverFilterHasEmail", v);
  const setPerPage = (v) => settings.setField("discoverPerPage", v);
  const setSearch = (v) => settings.setField("discoverSearch", v);

  // Local-only UI refs (don't need to survive tab switch)
  const keywordsRef = useRef(null);

  // Saved searches helpers
  const savedSearches = settings.savedSearches || [];
  const usedKeywords = settings.usedKeywords || [];

  const isCurrentSaved = savedSearches.some(
    s => s.keywords === keywords.trim() && s.location === location.trim()
  );

  function saveSearch() {
    if (!keywords.trim()) return;
    const entry = {
      id: Date.now(),
      keywords: keywords.trim(),
      location: location.trim(),
    };
    // Deduplicate by keywords+location
    const existing = savedSearches.filter(
      s => !(s.keywords === entry.keywords && s.location === entry.location)
    );
    settings.setField("savedSearches", [entry, ...existing]);
  }

  function removeSavedSearch(id) {
    settings.setField("savedSearches", savedSearches.filter(s => s.id !== id));
  }

  function applySearch(s) {
    setKeywords(s.keywords);
    setLocation(s.location);
  }

  function recordUsedKeywords(kw) {
    // Store individual comma-separated keywords for autocomplete
    const newKws = kw.split(",").map(k => k.trim()).filter(Boolean);
    const merged = [...new Set([...newKws, ...usedKeywords])].slice(0, 40);
    settings.setField("usedKeywords", merged);
  }

  // Keyword suggestions — filter usedKeywords by what's being typed in the last segment
  const currentSegment = keywords.split(",").pop().trim().toLowerCase();
  const suggestions = currentSegment.length >= 1
    ? usedKeywords.filter(k =>
        k.toLowerCase().includes(currentSegment) &&
        !keywords.split(",").map(s => s.trim()).includes(k)
      ).slice(0, 6)
    : [];

  // scanningUrl lives in store so scan-in-progress indicator survives tab switch
  const scanningUrl = ds.scanningUrl || null;
  const setScanningUrl = (v) => ds.setField("scanningUrl", v);




  const loadSessions = useCallback(async () => {
    try {
      const data = await api.getSessions();
      setSessions(data.sessions || []);
    } catch {}
  }, []);

  const loadRecords = useCallback(async (sessionId) => {
    setLoading(true);
    ds.setField("selected", []);
    try {
      const data = await api.getProspects(sessionId, sortBy, sortDir, filterStatus, filterHasEmail, discoverSearch);
      setRecords(data.records || []);
      setPage(1);
    } catch (e) {
      console.error("load prospects failed:", e);
    } finally {
      setLoading(false);
    }
  }, [sortBy, sortDir, filterStatus, filterHasEmail, discoverSearch]);

  useEffect(() => { loadSessions(); }, []);
  useEffect(() => { if (activeSession !== undefined) loadRecords(activeSession); }, [activeSession, sortBy, sortDir, filterStatus, filterHasEmail, discoverSearch]);

  function handleSort(field) {
    if (sortBy === field) setSortDir(sortDir === "desc" ? "asc" : "desc");
    else { setSortBy(field); setSortDir("desc"); }
    setPage(1);
  }

  async function handleSearch() {
    if (!keywords.trim() || searching) return;
    setSearching(true);
    setSearchError(null);
    setSearchStats(null);
    setSearchProgress({ phase: "starting", scrolled: 0, detailed: 0, total: 0, withWebsite: 0, keyword: "" });
    recordUsedKeywords(keywords.trim());

    try {
      const result = await api.discoverSearch(keywords.trim(), location.trim(), limit, (event) => {
        useDiscoverStore.getState().setField("searchProgress", (() => {
          const p = useDiscoverStore.getState().searchProgress || { scrolled: 0, detailed: 0, total: 0, withWebsite: 0, keyword: "" };
          if (event.type === "keyword_start") return { ...p, phase: "scrolling", keyword: event.keyword, scrolled: 0 };
          if (event.type === "scroll") return { ...p, phase: "scrolling", scrolled: event.count, keyword: event.keyword };
          if (event.type === "detail") return { ...p, phase: "details", detailed: event.index, total: event.total, withWebsite: p.withWebsite + (event.website ? 1 : 0), keyword: event.keyword, lastName: event.name };
          if (event.type === "keyword_done") return { ...p, phase: "done_keyword" };
          return p;
        })());
      });

      setSearchStats(result);
      await loadSessions();
      setActiveSession(result.session_id);
    } catch (e) {
      setSearchError(e.message || "Search failed");
    } finally {
      setSearching(false);
      setSearchProgress(null);
    }
  }

  async function scanProspect(record) {
    const url = record.website;
    if (!url) return;

    setScanningUrl(url);
    await api.updateProspectStatus(url, "scanning");
    ds.updateRecord(url, { status: "scanning" });

    try {
      const result = await api.analyzePage(url, getScanSettings(), `discover-${Date.now()}`, null, "shallow", settings.visionMode);

      const foundEmail = result.emails_found?.[0];
      const emailToUse = record.email || foundEmail || (() => {
        try { return `info@${new URL(url).hostname.replace(/^www\./, "")}`; } catch { return null; }
      })();

      if (emailToUse && !record.email) {
        await api.updateProspectEmail(url, emailToUse);
      }

      // Register in scan store WITHOUT switching to results tab
      const runId = scanStore.startShallow(url);
      scanStore.finishShallowSilent(runId, result);

      if (emailToUse) emailStore.setRecipient(url, emailToUse);
      if (settings.autoGenerateEmail) {
        emailStore.generate(url, result, getEmailSettings());
      }

      await api.updateProspectStatus(url, "scanned");
      ds.updateRecord(url, { status: "scanned", email: emailToUse || record.email });
    } catch (e) {
      await api.updateProspectStatus(url, "new");
      ds.updateRecord(url, { status: "new" });
      console.error("scan failed:", e);
    } finally {
      setScanningUrl(null);
    }
  }

  async function scanSelected() {
    // Mark all selected new records as queued immediately so user sees the queue
    const toScan = records.filter(r => selected.has(r.website) && ["new", "pending"].includes(r.status) && r.website);
    for (const r of toScan) {
      await api.updateProspectStatus(r.website, "queued");
      ds.updateRecord(r.website, { status: "queued" });
    }
    setSelected(new Set());

    // Process sequentially — each item moves scanning → scanned as it's processed
    for (const r of toScan) {
      await scanProspect({ ...r, status: "queued" });
    }
  }

  async function deleteSelected() {
    for (const website of selected) {
      await api.deleteProspect(website);
    }
    setRecords(rs => rs.filter(r => !selected.has(r.website)));
    setSelected(new Set());
  }

  async function markContactSelected() {
    for (const website of selected) {
      await api.updateProspectStatus(website, "dont_contact");
      ds.updateRecord(website, { status: "dont_contact" });
    }
    setRecords(rs => rs.map(r => selected.has(r.website) ? { ...r, status: "dont_contact" } : r));
    setSelected(new Set());
  }

  async function dismissProspect(website, e) {
    e.stopPropagation();
    await api.deleteProspect(website);
    setRecords(rs => rs.filter(r => r.website !== website));
    setSelected(s => { const n = new Set(s); n.delete(website); return n; });
  }

  function toggleSelect(website) {
    setSelected(s => {
      const n = new Set(s);
      if (n.has(website)) n.delete(website); else n.add(website);
      return n;
    });
  }

  function toggleSelectAll() {
    const pageUrls = paginated.map(r => r.website).filter(Boolean);
    const allSelected = pageUrls.every(u => selected.has(u));
    setSelected(s => {
      const n = new Set(s);
      if (allSelected) pageUrls.forEach(u => n.delete(u));
      else pageUrls.forEach(u => n.add(u));
      return n;
    });
  }

  function mapsUrl(rec) {
    // Build a proper Google Maps search URL using name + address for accuracy
    const q = [rec.name, rec.address].filter(Boolean).join(", ");
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`;
  }

  const hasFilters = filterStatus !== "all" || filterHasEmail !== "all" || discoverSearch !== "";
  const newCount = records.filter(r => r.status === "new").length;
  const unscannedCount = records.filter(r => ["new", "pending", "queued"].includes(r.status)).length;

  // Pagination
  const totalPages = perPage === 0 ? 1 : Math.ceil(records.length / perPage);
  const paginated = perPage === 0 ? records : records.slice((page - 1) * perPage, page * perPage);
  const pageUrls = paginated.map(r => r.website).filter(Boolean);
  const allPageSelected = pageUrls.length > 0 && pageUrls.every(u => selected.has(u));

  return (
    <div className="content">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>

        {/* Header */}
        <div style={{ marginBottom: 24 }}>
          <h1 style={{ fontSize: 22, fontWeight: 800, marginBottom: 6, letterSpacing: "-0.4px" }}>Discover</h1>
          <p className="text-muted text-sm">Find Japanese businesses on Google Maps and queue them for scanning.</p>
        </div>

        {/* Saved searches strip */}
        <AnimatePresence>
          {savedSearches.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              style={{ marginBottom: 12, display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
              <span style={{ fontSize: 11, color: "var(--ink3)", fontFamily: "var(--font-mono)", flexShrink: 0 }}>
                Saved:
              </span>
              {savedSearches.map(s => (
                <motion.div key={s.id}
                  initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  style={{
                    display: "flex", alignItems: "center", gap: 4,
                    padding: "3px 8px 3px 10px", borderRadius: 99,
                    border: `1px solid ${isCurrentSaved && s.keywords === keywords.trim() && s.location === location.trim() ? "var(--blue-line)" : "var(--border)"}`,
                    background: isCurrentSaved && s.keywords === keywords.trim() && s.location === location.trim() ? "var(--blue-glow)" : "var(--surface)",
                    fontSize: 11, cursor: "pointer",
                  }}>
                  <span onClick={() => applySearch(s)}
                    style={{ color: "var(--ink2)", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {s.keywords}
                    {s.location && <span style={{ color: "var(--ink3)", marginLeft: 4 }}>· {s.location}</span>}
                  </span>
                  <button onClick={() => removeSavedSearch(s.id)}
                    style={{ background: "none", border: "none", cursor: "pointer", padding: 0, display: "flex", color: "var(--ink3)", marginLeft: 2 }}>
                    <X size={10} />
                  </button>
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Search form */}
        <div className="panel mb-24">
          <div className="panel-header"><h2>Search Google Maps</h2></div>
          <div className="panel-body">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
              <div className="field">
                <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <Search size={11} /> Keywords
                </label>
                <div style={{ position: "relative" }}>
                  <input
                    ref={keywordsRef}
                    value={keywords}
                    onChange={e => { setKeywords(e.target.value); setShowSuggestions(true); }}
                    onFocus={() => setShowSuggestions(true)}
                    onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
                    onKeyDown={e => e.key === "Enter" && handleSearch()}
                    placeholder="ツアー, キャンプ, アクティビティ"
                    disabled={searching}
                    style={{ width: "100%" }}
                  />
                  {/* Keyword autocomplete dropdown */}
                  <AnimatePresence>
                    {showSuggestions && suggestions.length > 0 && (
                      <motion.div
                        initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                        style={{
                          position: "absolute", top: "100%", left: 0, right: 0, zIndex: 50,
                          background: "var(--surface)", border: "1px solid var(--border)",
                          borderRadius: "var(--radius)", boxShadow: "0 4px 16px rgba(0,0,0,0.3)",
                          marginTop: 2, overflow: "hidden",
                        }}>
                        {suggestions.map(kw => (
                          <div key={kw}
                            onMouseDown={() => {
                              // Replace last segment with the selected suggestion
                              const parts = keywords.split(",");
                              parts[parts.length - 1] = " " + kw;
                              setKeywords(parts.join(",").replace(/^,\s*/, ""));
                              setShowSuggestions(false);
                            }}
                            style={{
                              padding: "7px 12px", fontSize: 12, cursor: "pointer",
                              color: "var(--ink2)", borderBottom: "1px solid var(--border)",
                            }}
                            onMouseEnter={e => e.currentTarget.style.background = "var(--bg3)"}
                            onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                            {kw}
                          </div>
                        ))}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </div>
              <div className="field">
                <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <MapPin size={11} /> Location
                </label>
                <input
                  value={location}
                  onChange={e => setLocation(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleSearch()}
                  placeholder="北海道, ニセコ, Hokkaido Niseko"
                  disabled={searching}
                />
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div className="field" style={{ margin: 0 }}>
                <label style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 4, display: "block" }}>Result limit</label>
                <div style={{ display: "flex", gap: 6 }}>
                  {LIMIT_OPTIONS.map(opt => (
                    <button key={opt.value}
                      onClick={() => setLimit(opt.value)}
                      disabled={searching}
                      style={{
                        padding: "4px 12px", fontSize: 12, borderRadius: 6,
                        border: `1px solid ${limit === opt.value ? "var(--blue-line)" : "var(--border)"}`,
                        background: limit === opt.value ? "var(--blue-glow)" : "var(--surface)",
                        color: limit === opt.value ? "var(--blue)" : "var(--ink2)",
                        cursor: "pointer", fontWeight: limit === opt.value ? 700 : 400,
                      }}>
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
                {/* Save current search */}
                <motion.button
                  whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                  onClick={saveSearch}
                  disabled={!keywords.trim() || searching}
                  title={isCurrentSaved ? "Already saved" : "Save this search"}
                  className="btn btn--ghost btn--sm"
                  style={{ color: isCurrentSaved ? "var(--blue)" : "var(--ink3)" }}>
                  {isCurrentSaved
                    ? <Bookmark size={14} style={{ fill: "var(--blue)", color: "var(--blue)" }} />
                    : <Bookmark size={14} />}
                </motion.button>
                <button className="btn btn--primary" onClick={handleSearch}
                  disabled={!keywords.trim() || searching}>
                  {searching
                    ? <><div className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }} /> Searching…</>
                    : <><Search size={13} /> Search</>}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Progress card — full width, below search panel, slides in */}
        <AnimatePresence>
          {searching && searchProgress && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.2 }}
              className="mb-24"
              style={{
                background: "var(--surface)",
                border: "1px solid var(--blue-line)",
                borderRadius: "var(--radius)",
                overflow: "hidden",
              }}>

              {/* Top: spinner + phase label + counter */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px 10px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                  <div className="spinner" style={{ width: 15, height: 15, borderWidth: 2, flexShrink: 0 }} />
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--ink1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {searchProgress.phase === "starting" && "Connecting to Google Maps…"}
                    {searchProgress.phase === "scrolling" && `Loading results for "${searchProgress.keyword}"`}
                    {searchProgress.phase === "details" && `Getting details — "${searchProgress.keyword}"`}
                    {searchProgress.phase === "done_keyword" && "Moving to next keyword…"}
                  </span>
                </div>
                <span style={{ fontSize: 13, fontFamily: "var(--font-mono)", color: "var(--blue)", fontWeight: 700, flexShrink: 0, marginLeft: 16 }}>
                  {searchProgress.phase === "scrolling" && `${searchProgress.scrolled} found`}
                  {searchProgress.phase === "details" && `${searchProgress.detailed} / ${searchProgress.total}`}
                </span>
              </div>

              {/* Progress bar — flush, full width, fills left to right */}
              <div style={{ height: 6, background: "rgba(255,255,255,0.08)", position: "relative", overflow: "hidden" }}>
                {searchProgress.phase === "details" && searchProgress.total > 0 ? (
                  <motion.div
                    animate={{ width: `${Math.round((searchProgress.detailed / searchProgress.total) * 100)}%` }}
                    transition={{ duration: 0.35, ease: "easeOut" }}
                    style={{ position: "absolute", inset: "0 auto 0 0", background: "var(--blue)", boxShadow: "0 0 8px var(--blue)" }}
                  />
                ) : (
                  /* Indeterminate shimmer during scroll phase */
                  <motion.div
                    animate={{ x: ["-50%", "150%"] }}
                    transition={{ repeat: Infinity, duration: 1.4, ease: "easeInOut" }}
                    style={{ position: "absolute", top: 0, bottom: 0, width: "50%",
                      background: "linear-gradient(90deg, transparent, var(--blue), transparent)" }}
                  />
                )}
              </div>

              {/* Bottom: last business name + website count */}
              <div style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "8px 16px", borderTop: "1px solid var(--border)", background: "var(--bg3)",
              }}>
                <span style={{ fontSize: 11, color: "var(--ink3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1, minWidth: 0 }}>
                  {searchProgress.lastName ? `↳ ${searchProgress.lastName}` : "Starting…"}
                </span>
                <div style={{ display: "flex", gap: 16, flexShrink: 0, marginLeft: 16, alignItems: "center" }}>
                  {searchProgress.withWebsite > 0 && (
                    <span style={{ fontSize: 11, color: "var(--ink3)" }}>
                      <span style={{ color: "var(--blue)", fontWeight: 700 }}>{searchProgress.withWebsite}</span> with website
                    </span>
                  )}
                  <span style={{ fontSize: 11, color: "var(--ink3)" }}>Don't close this tab</span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Search stats / error */}
        <AnimatePresence>
          {searchStats && (
            <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
              className="mb-24"
              style={{ padding: "8px 12px", background: "var(--blue-glow)",
                border: "1px solid var(--blue-line)", borderRadius: "var(--radius)", fontSize: 12 }}>
              Found <strong>{searchStats.total_found}</strong> businesses ·{" "}
              <strong>{searchStats.saved}</strong> new ·{" "}
              <span style={{ color: "var(--ink3)" }}>
                {searchStats.skipped_no_website} no website · {searchStats.skipped_already_scanned} already scanned (skipped)
              </span>
            </motion.div>
          )}
          {searchError && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="alert alert--error mb-24">
              <AlertCircle size={13} /> {searchError}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Session picker + results */}
        {sessions.length > 0 && (
          <>
            {/* Session tabs */}
            <div style={{ display: "flex", gap: 6, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
              <span style={{ fontSize: 11, color: "var(--ink3)", fontFamily: "var(--font-mono)" }}>Sessions:</span>
              <button
                onClick={() => setActiveSession(null)}
                style={{
                  padding: "3px 10px", fontSize: 11, borderRadius: 99, cursor: "pointer",
                  border: `1px solid ${activeSession === null ? "var(--blue-line)" : "var(--border)"}`,
                  background: activeSession === null ? "var(--blue-glow)" : "var(--surface)",
                  color: activeSession === null ? "var(--blue)" : "var(--ink3)",
                  fontFamily: "var(--font-mono)",
                }}>All</button>
              {sessions.map(s => (
                <button key={s.session_id}
                  onClick={() => setActiveSession(s.session_id)}
                  title={`${s.keywords}${s.location ? " · " + s.location : ""}`}
                  style={{
                    padding: "3px 10px", fontSize: 11, borderRadius: 99, cursor: "pointer",
                    border: `1px solid ${activeSession === s.session_id ? "var(--blue-line)" : "var(--border)"}`,
                    background: activeSession === s.session_id ? "var(--blue-glow)" : "var(--surface)",
                    color: activeSession === s.session_id ? "var(--blue)" : "var(--ink3)",
                    fontFamily: "var(--font-mono)",
                  }}>
                  {s.keywords.split(",")[0].trim()}
                  {s.location ? ` · ${s.location}` : ""}
                  <span style={{ marginLeft: 5, opacity: 0.6 }}>({s.count})</span>
                </button>
              ))}
            </div>

            {/* Toolbar */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
              <span style={{ fontSize: 12, color: "var(--ink3)" }}>
                {records.length} prospect{records.length !== 1 ? "s" : ""}
                {unscannedCount > 0 && <span style={{ color: "var(--blue)", marginLeft: 6 }}>{unscannedCount} unscanned</span>}
              </span>

              {/* Bulk actions */}
              <AnimatePresence>
                {selected.size > 0 && (
                  <motion.div initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }}
                    style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <span style={{ fontSize: 11, color: "var(--blue)", fontWeight: 600, marginLeft: 4 }}>
                      {selected.size} selected
                    </span>
                    <button className="btn btn--sm btn--primary" onClick={scanSelected} disabled={!!scanningUrl}
                      title="Scan selected">
                      <ScanLine size={12} /> Scan
                    </button>
                    <button className="btn btn--sm btn--ghost" onClick={markContactSelected}
                      title="Mark Don't Contact">
                      <Ban size={12} /> Don't Contact
                    </button>
                    <button className="btn btn--sm btn--ghost" onClick={deleteSelected}
                      style={{ color: "#ef4444" }}>
                      <Trash2 size={12} /> Delete
                    </button>
                    <button className="btn btn--sm btn--ghost" onClick={() => setSelected(new Set())}>
                      Clear
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>

              <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontSize: 11, color: "var(--ink3)" }}>Per page:</span>
                  <select value={perPage} onChange={e => { setPerPage(Number(e.target.value)); setPage(1); }}
                    style={{ fontSize: 11, padding: "3px 6px", borderRadius: 4, border: "1px solid var(--border)", background: "var(--bg3)", color: "var(--ink2)" }}>
                    {PER_PAGE_OPTIONS.map(n => <option key={n} value={n}>{n}</option>)}
                    <option value={0}>All</option>
                  </select>
                </div>
                <button className={`btn btn--sm ${hasFilters ? "btn--primary" : "btn--ghost"}`}
                  onClick={() => setShowFilters(f => !f)}>
                  <Filter size={12} /> Filters
                </button>
                <button className="btn btn--ghost btn--sm"
                  onClick={() => loadRecords(activeSession)} disabled={loading}>
                  <RefreshCw size={12} className={loading ? "spin" : ""} /> Refresh
                </button>
              </div>
            </div>

            {/* Filter bar */}
            <AnimatePresence>
              {showFilters && (
                <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }} style={{ overflow: "hidden", marginBottom: 12 }}>
                  <div style={{
                    display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center",
                    padding: "10px 14px", background: "var(--surface)",
                    border: "1px solid var(--border)", borderRadius: "var(--radius)",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <input
                        type="text"
                        placeholder="Search name or URL..."
                        value={discoverSearch}
                        onChange={e => { setSearch(e.target.value); setPage(1); }}
                        style={{ width: 140, fontSize: 11, padding: "4px 8px", borderRadius: 4, border: "1px solid var(--border)", background: "var(--bg3)", color: "var(--ink1)" }}
                      />
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 11, color: "var(--ink3)", fontWeight: 600 }}>STATUS</span>
                      <select value={filterStatus} onChange={e => { setFilterStatus(e.target.value); setPage(1); }}
                        style={{ fontSize: 11, padding: "3px 6px", borderRadius: 4, border: "1px solid var(--border)", background: "var(--bg3)", color: "var(--ink2)" }}>
                        <option value="all">All</option>
                        <option value="new">New</option>
                        <option value="pending">Unscanned</option>
                        <option value="queued">Queued</option>
                        <option value="scanned">Scanned</option>
                        <option value="emailed">Emailed</option>
                        <option value="scheduled">Scheduled</option>
                        <option value="skipped">Skipped</option>
                        <option value="bounced">Bounced (Retry)</option>
                        <option value="cant_deliver">Can't Deliver</option>
                        <option value="dont_contact">Don't Contact</option>
                      </select>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 11, color: "var(--ink3)", fontWeight: 600 }}>EMAIL</span>
                      <select value={filterHasEmail} onChange={e => { setFilterHasEmail(e.target.value); setPage(1); }}
                        style={{ fontSize: 11, padding: "3px 6px", borderRadius: 4, border: "1px solid var(--border)", background: "var(--bg3)", color: "var(--ink2)" }}>
                        <option value="all">All</option>
                        <option value="yes">Has email</option>
                        <option value="no">No email</option>
                      </select>
                    </div>
                    {hasFilters && (
                      <button className="btn btn--ghost btn--sm" onClick={() => { setFilterStatus("all"); setFilterHasEmail("all"); setSearch(""); setPage(1); }}>
                        Clear
                      </button>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Results table */}
            {records.length === 0 && !loading ? (
              <div style={{ textAlign: "center", padding: "60px 0", color: "var(--ink3)" }}>
                <Inbox size={36} style={{ marginBottom: 10, opacity: 0.4 }} />
                <p style={{ margin: 0, fontSize: 14 }}>No prospects yet. Run a search above.</p>
              </div>
            ) : (
              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", overflow: "hidden" }}>

                {/* Header */}
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "32px 2fr 90px 80px 110px 160px 80px 76px",
                  padding: "8px 16px", borderBottom: "1px solid var(--border)",
                  background: "var(--bg3)", fontSize: 10, fontWeight: 700,
                  letterSpacing: "0.08em", textTransform: "uppercase",
                }}>
                  <div style={{ display: "flex", alignItems: "center", cursor: "pointer" }} onClick={toggleSelectAll}
                    title={allPageSelected ? "Deselect all on page" : "Select all on page"}>
                    {allPageSelected
                      ? <CheckSquare size={13} style={{ color: "var(--blue)" }} />
                      : <Square size={13} style={{ color: "var(--ink3)" }} />}
                  </div>
                  <SortHeader label="Business" field="name" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
                  <SortHeader label="Rating" field="rating" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
                  <span style={{ color: "var(--ink3)" }}>Category</span>
                  <span style={{ color: "var(--ink3)" }}>Email</span>
                  <span style={{ color: "var(--ink3)" }}>Website</span>
                  <SortHeader label="Status" field="status" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
                  <span style={{ color: "var(--ink3)" }}>Actions</span>
                </div>

                {/* Rows */}
                <AnimatePresence initial={false}>
                  {paginated.map((rec, i) => {
                    const isScanning = scanningUrl === rec.website;
                    const isSelected = selected.has(rec.website);
                    return (
                      <motion.div key={rec.website || i}
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                        transition={{ delay: i * 0.01 }}
                        style={{
                          display: "grid",
                          gridTemplateColumns: "32px 2fr 90px 80px 110px 160px 80px 76px",
                          padding: "10px 16px", alignItems: "center",
                          borderBottom: i < paginated.length - 1 ? "1px solid var(--border)" : "none",
                          background: isSelected ? "var(--blue-glow)" : isScanning ? "rgba(59,130,246,0.06)" : "transparent",
                          transition: "background 0.1s",
                        }}>

                        {/* Checkbox */}
                        <div style={{ display: "flex", alignItems: "center", cursor: "pointer" }}
                          onClick={() => rec.website && toggleSelect(rec.website)}>
                          {isSelected
                            ? <CheckSquare size={13} style={{ color: "var(--blue)" }} />
                            : <Square size={13} style={{ color: "var(--ink3)" }} />}
                        </div>

                        {/* Name + address */}
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {rec.name}
                          </div>
                          {rec.address && (
                            <div style={{ fontSize: 10, color: "var(--ink3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginTop: 2 }}>
                              {rec.address}
                            </div>
                          )}
                        </div>

                        {/* Rating */}
                        <div style={{ display: "flex", alignItems: "center", gap: 3 }}>
                          <RatingStars rating={rec.rating} />
                          {rec.review_count && <span style={{ fontSize: 10, color: "var(--ink3)" }}>({rec.review_count})</span>}
                        </div>

                        {/* Category */}
                        <div style={{ fontSize: 11, color: "var(--ink3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {rec.category || "—"}
                        </div>

                        {/* Email */}
                        <div style={{ fontSize: 11, color: rec.email ? "var(--ink2)" : "var(--ink3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontFamily: "var(--font-mono)" }}>
                          {rec.email || "—"}
                        </div>

                        {/* Website */}
                        <div style={{ minWidth: 0 }}>
                          {rec.website ? (
                            <a href={rec.website} target="_blank" rel="noreferrer"
                              style={{ fontSize: 11, color: "var(--blue)", display: "flex", alignItems: "center", gap: 3, textDecoration: "none" }}
                              onClick={e => e.stopPropagation()}>
                              <Globe size={10} style={{ flexShrink: 0 }} />
                              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                {rec.website.replace(/^https?:\/\/(www\.)?/, "")}
                              </span>
                              <ExternalLink size={9} style={{ flexShrink: 0 }} />
                            </a>
                          ) : <span style={{ fontSize: 11, color: "var(--ink3)" }}>—</span>}
                        </div>

                        {/* Status */}
                        <div>
                          {isScanning
                            ? <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "var(--blue)" }}>
                                <div className="spinner" style={{ width: 10, height: 10, borderWidth: 1.5 }} /> Scanning
                              </span>
                            : <StatusBadge status={rec.status} />}
                        </div>

                        {/* Actions — right-aligned, consistent padding */}
                        <div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>
                          {rec.website && ["new", "pending"].includes(rec.status) && (
                            <motion.button whileHover={{ scale: 1.08 }} whileTap={{ scale: 0.94 }}
                              className="btn btn--sm btn--primary"
                              onClick={() => scanProspect(rec)}
                              disabled={!!scanningUrl}
                              title="Scan this site">
                              <ScanLine size={12} />
                            </motion.button>
                          )}
                          <motion.button whileHover={{ scale: 1.08 }} whileTap={{ scale: 0.94 }}
                            className={`btn btn--sm ${rec.status === "dont_contact" ? "btn--primary" : "btn--ghost"}`}
                            onClick={async (e) => {
                              e.stopPropagation();
                              const next = rec.status === "dont_contact" ? "pending" : "dont_contact";
                              await api.updateProspectStatus(rec.website, next);
                              setRecords(recs => recs.map(r => r.website === rec.website ? { ...r, status: next } : r));
                            }}
                            title="Toggle Don't Contact">
                            <Ban size={12} />
                          </motion.button>
                          {(rec.status === "emailed" || rec.email?.sent_at) && (
                            <motion.button whileHover={{ scale: 1.08 }} whileTap={{ scale: 0.94 }}
                              className="btn btn--sm btn--ghost"
                              onClick={async (e) => {
                                e.stopPropagation();
                                const res = await api.toggleResponse(rec.website);
                                setRecords(recs => recs.map(r => r.website === rec.website ? { ...r, email: { ...r.email, got_response: res.got_response } } : r));
                              }}
                              title="Toggle Response">
                              <MessageSquare size={12} style={{ color: rec.email?.got_response ? "var(--green)" : "inherit" }} />
                            </motion.button>
                          )}
                          {rec.status === "scanned" && (
                            <motion.button whileHover={{ scale: 1.08 }}
                              className="btn btn--sm btn--ghost"
                              onClick={async () => {
                                try {
                                  const full = await api.getHistoryEntry(rec.website);
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
                                    emails_found: full.emails_found || (rec.email ? [rec.email] : []),
                                    _fromHistory: true,
                                  };
                                  // Patch email store BEFORE finishShallow — finishShallow switches
                                  // tabs which opens the drawer, and the useEffect in EmailDrawer
                                  // reads the store immediately on open. Must be set first.
                                  const patch = { ...(useEmailStore.getState().emails[full.url] || {}) };
                                  if (full.email) {
                                    if (full.email.recipient) patch.recipientEmail = full.email.recipient;
                                    if (full.email.subject) patch.subject = full.email.subject;
                                    if (full.email.html) patch.htmlContent = full.email.html;
                                    if (full.email.sent_at) patch.sentAt = full.email.sent_at;
                                    patch.status = full.email.sent_at ? "sent" : full.email.html ? "ready" : undefined;
                                  }
                                  if (!patch.recipientEmail) {
                                    // Priority: prospect email (saved during scan) →
                                    // emails_found in DB (newer scans only) → info@domain
                                    let recipient = rec.email
                                      || (full.emails_found || [])[0];
                                    if (!recipient) {
                                      try {
                                        const domain = new URL(full.url).hostname.replace(/^www\./, "");
                                        recipient = `info@${domain}`;
                                      } catch {}
                                    }
                                    if (recipient) patch.recipientEmail = recipient;
                                  }
                                  if (Object.keys(patch).length > 0) {
                                    useEmailStore.setState(s => ({ emails: { ...s.emails, [full.url]: patch } }));
                                  }
                                  const runId = scanStore.startShallow(full.url);
                                  scanStore.finishShallow(runId, result);
                                } catch (e) {
                                  console.error("failed to load scan:", e);
                                }
                              }}
                              title="View results">
                              <CheckCircle size={12} style={{ color: "var(--green)" }} />
                            </motion.button>
                          )}
                          <a href={mapsUrl(rec)} target="_blank" rel="noreferrer"
                            className="btn btn--sm btn--ghost"
                            onClick={e => e.stopPropagation()}
                            title="Open in Google Maps">
                            <MapPin size={12} />
                          </a>
                          <motion.button whileHover={{ scale: 1.08 }}
                            className="btn btn--sm btn--ghost"
                            onClick={e => dismissProspect(rec.website, e)}
                            title="Delete">
                            <Trash2 size={12} />
                          </motion.button>
                        </div>
                      </motion.div>
                    );
                  })}
                </AnimatePresence>

                <PaginationFooter
                  page={page}
                  totalPages={totalPages}
                  total={records.length}
                  perPage={perPage}
                  onPage={setPage}
                />
              </div>
            )}
          </>
        )}

        {/* Empty state — no sessions yet */}
        {sessions.length === 0 && !searching && (
          <div style={{ textAlign: "center", padding: "80px 0", color: "var(--ink3)" }}>
            <Search size={40} style={{ marginBottom: 12, opacity: 0.3 }} />
            <p style={{ margin: 0, fontSize: 14 }}>Enter keywords and a location to discover businesses.</p>
            <p style={{ margin: "4px 0 0", fontSize: 12, opacity: 0.7 }}>
              e.g. keywords: "ツアー, アクティビティ" · location: "北海道 ニセコ"
            </p>
          </div>
        )}

      </motion.div>
    </div>
  );
}
