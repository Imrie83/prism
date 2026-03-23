import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Bot, ExternalLink, Mail, TrendingDown } from "lucide-react";
import { useScanStore } from "../stores/scanStore";
import { useAgentStore } from "../stores/agentStore";
import { useEmailStore } from "../stores/emailStore";
import ScoreRing from "../components/ScoreRing";
import IssueCard from "../components/IssueCard";
import ScreenshotLightbox from "../components/ScreenshotLightbox";
import TokenBadge from "../components/TokenBadge";
import { api } from "../lib/api";

// ── Tiny helpers ─────────────────────────────────────────────────────────────
function scoreColor(s) {
  return s >= 75 ? "var(--green)" : s >= 45 ? "var(--yellow)" : "var(--red)";
}

function SevCounts({ counts, totalIssues }) {
  if (!counts) return null;
  const shown = (counts.high || 0) + (counts.medium || 0) + (counts.low || 0);
  const hiddenCount = totalIssues && totalIssues > shown ? totalIssues - shown : 0;
  return (
    <div className="sev-counts">
      {counts.high > 0 && <div className="sev-counts__item sev-counts__item--high">▲ {counts.high} high</div>}
      {counts.medium > 0 && <div className="sev-counts__item sev-counts__item--medium">● {counts.medium} med</div>}
      {counts.low > 0 && <div className="sev-counts__item sev-counts__item--low">▼ {counts.low} low</div>}
      {hiddenCount > 0 && (
        <div className="sev-counts__item" style={{ color: "var(--ink3)", opacity: 0.7 }}>
          +{hiddenCount} more
        </div>
      )}
    </div>
  );
}

function EmailButton({ url }) {
  const { openDrawerFor } = useEmailStore();
  const emailData = useEmailStore(s => s.emails[url]);
  const statusCol = { generating: "var(--blue)", ready: "var(--green)", error: "var(--red)", queued: "var(--ink3)", sent: "var(--accent)" };
  const col = emailData ? statusCol[emailData.status] : null;
  return (
    <motion.button className="btn btn--ghost btn--sm" onClick={() => openDrawerFor(url)}
      whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }} style={{ position: "relative" }}>
      <Mail size={13} /> Write Email
      {col && (
        <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }}
          style={{ position: "absolute", top: -3, right: -3, width: 8, height: 8,
            borderRadius: "50%", background: col, boxShadow: `0 0 6px ${col}` }} />
      )}
    </motion.button>
  );
}

// ── Run history picker strip ──────────────────────────────────────────────────
function RunPicker({ runs, activeId, onSelect, onRemove }) {
  if (runs.length === 0) return null;
  return (
    <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 16, flexWrap: "wrap" }}>
      <span style={{ fontSize: 11, color: "var(--ink3)", fontFamily: "var(--font-mono)" }}>History:</span>
      {runs.map((run) => {
        const d = new Date(run.ts);
        const timeLabel = `${d.getHours()}:${String(d.getMinutes()).padStart(2,"0")}`;
        const isActive = run.runId === activeId;
        return (
          <div key={run.runId} style={{ display: "flex", alignItems: "center", gap: 0 }}>
            <motion.button
              onClick={() => onSelect(run.runId)}
              whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
              style={{
                padding: "3px 8px 3px 10px", fontSize: 11,
                borderRadius: onRemove ? "99px 0 0 99px" : 99,
                background: isActive ? "var(--blue-glow)" : "var(--surface)",
                border: `1px solid ${isActive ? "var(--blue-line)" : "var(--border)"}`,
                borderRight: onRemove ? "none" : undefined,
                color: isActive ? "var(--blue)" : "var(--ink3)",
                fontFamily: "var(--font-mono)", cursor: "pointer",
              }}>
              {timeLabel}
            </motion.button>
            {onRemove && (
              <motion.button
                onClick={() => onRemove(run.runId)}
                whileHover={{ scale: 1.1, background: "rgba(248,113,113,0.15)" }}
                title="Remove this run"
                style={{
                  padding: "3px 7px", fontSize: 11, lineHeight: 1,
                  borderRadius: "0 99px 99px 0",
                  background: isActive ? "var(--blue-glow)" : "var(--surface)",
                  border: `1px solid ${isActive ? "var(--blue-line)" : "var(--border)"}`,
                  color: "var(--ink3)", cursor: "pointer",
                }}>
                ×
              </motion.button>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Aside panel ───────────────────────────────────────────────────────────────
function ResultAside({ result, onLightbox, animate = true }) {
  return (
    <div style={{ position: "sticky", top: 72, display: "flex", flexDirection: "column", gap: 14 }}>
      <motion.div className="panel panel--glow"
        initial={animate ? { opacity: 0, scale: 0.92 } : {}}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4, delay: 0.1, type: "spring", stiffness: 200 }}>
        <div className="panel-header"><h2>Score</h2></div>
        <div className="panel-body" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}>
          <ScoreRing score={result.score ?? 0} size={120} />
          <SevCounts counts={result.issueCounts} totalIssues={result.totalIssues} />
        </div>
      </motion.div>

      {result.screenshot && (
        <motion.div className="panel"
          initial={animate ? { opacity: 0, y: 12 } : {}} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.25 }}>
          <div className="panel-header">
            <h2>Screenshot</h2>
            <span style={{ fontSize: 11, color: "var(--ink3)" }}>click to enlarge</span>
          </div>
          <div className="screenshot-frame" style={{ borderRadius: 0, border: "none", cursor: "zoom-in" }}
            onClick={() => onLightbox(result.screenshot, result.url)}>
            <img src={`data:image/jpeg;base64,${result.screenshot}`} alt="Page screenshot" />
          </div>
        </motion.div>
      )}

      {result.summary && (
        <motion.div className="panel"
          initial={animate ? { opacity: 0, y: 12 } : {}} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.35 }}>
          <div className="panel-header"><h2>Summary</h2></div>
          <div className="panel-body">
            <p style={{ fontSize: 13, color: "var(--ink2)", lineHeight: 1.7 }}>{result.summary}</p>
          </div>
        </motion.div>
      )}
    </div>
  );
}

function IssueList({ issues, scanResult }) {
  const emailStore = useEmailStore();
  const url = scanResult?.url;
  const emailData = useEmailStore(s => url ? s.emails[url] : null);

  // Default checked set:
  // - If email was generated after this change, checkedIssues is already stored
  // - If email pre-existed (no checkedIssues stored), default to first 5 by original index
  const allIndices = issues.map((_, i) => i);
  const checkedIssues = emailData?.checkedIssues ?? allIndices.slice(0, 5);

  const sorted = [...issues].map((issue, origIndex) => ({ issue, origIndex }))
    .sort((a, b) => {
      const o = { high: 0, medium: 1, low: 2 };
      return (o[a.issue.severity] ?? 3) - (o[b.issue.severity] ?? 3);
    });

  const hasEmail = !!emailData?.htmlContent;

  const handleCheck = useCallback(async (origIndex, checked) => {
    if (!url || !scanResult) return;
    const next = checked
      ? [...new Set([...checkedIssues, origIndex])].sort((a, b) => a - b)
      : checkedIssues.filter(i => i !== origIndex);
    emailStore.setCheckedIssues(url, next);
    if (!hasEmail) return;
    try {
      const { card_block } = await api.rebuildCard(scanResult, next);
      const currentHtml = emailStore.getEmail(url)?.htmlContent || "";
      // Replace only the sentinel-wrapped card block — safe even if called multiple times
      const updated = currentHtml.includes("<!--SHINRAI-CARD-START-->")
        ? currentHtml.replace(/<!--SHINRAI-CARD-START-->[\s\S]*?<!--SHINRAI-CARD-END-->/, card_block)
        : currentHtml; // no sentinel = old email, can't safely replace, leave as-is
      emailStore.setHtmlContent(url, updated);
    } catch (e) {
      console.warn("[IssueList] card rebuild failed:", e.message);
    }
  }, [url, scanResult, checkedIssues, hasEmail, emailStore]);

  return (
    <div>
      {hasEmail && (
        <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
          <Mail size={11} />
          Check issues to include in email report card
        </div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
        {sorted.map(({ issue, origIndex }, i) => (
          <IssueCard
            key={origIndex}
            issue={issue}
            defaultOpen={i === 0}
            index={i}
            checked={hasEmail ? checkedIssues.includes(origIndex) : undefined}
            onCheckedChange={hasEmail ? (val) => handleCheck(origIndex, val) : undefined}
          />
        ))}
      </div>
    </div>
  );
}

// ── Shallow results ───────────────────────────────────────────────────────────
function ShallowView({ onLightbox }) {
  const { shallowHistory, shallowActiveRun, setShallowActiveRun, removeShallowRun } = useScanStore();
  const run = shallowHistory.find(r => r.runId === shallowActiveRun) || shallowHistory[0];
  if (!run?.result) return <Scanning />;
  const result = run.result;

  return (
    <>
      <RunPicker runs={shallowHistory} activeId={run.runId} onSelect={setShallowActiveRun} onRemove={removeShallowRun} />

      {/* URL / title header */}
      {result.url && (
        <div className="batch-page-header" style={{ marginBottom: 16 }}>
          <div className="batch-page-header__left">
            <div className="batch-page-header__title">{result.title || result.url}</div>
            <a href={result.url} target="_blank" rel="noopener noreferrer" className="batch-page-header__url">
              {result.url} <ExternalLink size={10} />
            </a>
          </div>
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <h2 style={{ fontSize: 13, fontWeight: 600, color: "var(--ink2)" }}>
              {result.issues?.length ?? 0} issue{result.issues?.length !== 1 ? "s" : ""} found
            </h2>
            <TokenBadge tokens={result._tokens} costType="audit" />
          </div>
          <EmailButton url={result.url} />
      </div>
      <div className="results-layout">
        <div className="results-layout__main"><IssueList issues={result.issues || []} scanResult={result} /></div>
        <div className="results-layout__aside"><ResultAside result={result} onLightbox={onLightbox} /></div>
      </div>
    </>
  );
}

// ── Deep results ──────────────────────────────────────────────────────────────
function DeepView({ onLightbox }) {
  const { deepHistory, deepActiveRun, setDeepActiveRun, removeDeepRun, status } = useScanStore();
  const run = deepHistory.find(r => r.runId === deepActiveRun) || deepHistory[0];
  const [activePage, setActivePage] = useState(0);

  if (!run) return <Scanning />;

  const pages = run.pages || [];
  const page = pages[activePage];

  return (
    <>
      <RunPicker runs={deepHistory} activeId={run.runId} onSelect={(id) => { setDeepActiveRun(id); setActivePage(0); }} onRemove={removeDeepRun} />

      {/* Overall score banner */}
      {run.overallScore != null && (
        <motion.div className="panel panel--glow" style={{ marginBottom: 20 }}
          initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
          <div className="panel-body" style={{ display: "flex", alignItems: "center", gap: 24, padding: "16px 24px" }}>
            <div>
              <div style={{ fontSize: 11, color: "var(--ink3)", fontFamily: "var(--font-mono)", marginBottom: 4 }}>
                OVERALL SITE SCORE
              </div>
              <div style={{ fontSize: 36, fontWeight: 800, color: scoreColor(run.overallScore), letterSpacing: "-1px" }}>
                {run.overallScore}
                <span style={{ fontSize: 16, color: "var(--ink3)", fontWeight: 400 }}>/100</span>
              </div>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, color: "var(--ink3)", marginBottom: 8 }}>
                {pages.length} page{pages.length !== 1 ? "s" : ""} analysed · {run.url}
              </div>
              {/* Mini score bars per page */}
              <div style={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
                {pages.map((p, i) => (
                  <motion.button key={i}
                    onClick={() => setActivePage(i)}
                    whileHover={{ scale: 1.1 }}
                    title={p.url}
                    style={{
                      width: 28, height: 28, borderRadius: 4,
                      background: p.result?.score != null ? scoreColor(p.result.score) : "var(--border)",
                      opacity: activePage === i ? 1 : 0.5,
                      border: activePage === i ? "2px solid white" : "2px solid transparent",
                      cursor: "pointer", fontSize: 9, fontWeight: 700,
                      color: activePage === i ? "#fff" : "rgba(255,255,255,0.7)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                    }}>
                    {p.result?.score ?? "?"}
                  </motion.button>
                ))}
                {status === "scanning" && (
                  <div style={{ width: 28, height: 28, borderRadius: 4, background: "var(--border)",
                    display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <div className="spinner" style={{ width: 10, height: 10, borderWidth: 1.5 }} />
                  </div>
                )}
              </div>
            </div>
          </div>
        </motion.div>
      )}

      {/* Per-page tab nav */}
      <div className="batch-nav" style={{ marginBottom: 16 }}>
        {pages.map((p, i) => (
          <motion.button key={i}
            className={`batch-nav__item${activePage === i ? " batch-nav__item--active" : ""}`}
            onClick={() => changePage(i)}
            whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}>
            <span>#{i + 1}</span>
            {p.result?.score != null && (
              <span className="batch-nav__item__score" style={{ color: scoreColor(p.result.score) }}>
                {p.result.score}
              </span>
            )}
          </motion.button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {page && (
          <motion.div key={activePage}
            initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -12 }} transition={{ duration: 0.18 }}>

            <div className="batch-page-header">
              <div className="batch-page-header__left">
                <div className="batch-page-header__num">Page {activePage + 1} of {pages.length}</div>
                <div className="batch-page-header__title">{page.result?.title || page.url}</div>
                <a href={page.url} target="_blank" rel="noopener noreferrer" className="batch-page-header__url">
                  {page.url} <ExternalLink size={10} />
                </a>
              </div>
              {page.result && <ScoreRing score={page.result.score ?? 0} size={88} />}
            </div>

            {page.result ? (
              <div className="results-layout">
                <div className="results-layout__main">
                  <IssueList issues={page.result.issues || []} scanResult={page.result} />
                  {!page.result.issues?.length && <div style={{ fontSize: 13, color: "var(--ink3)", padding: "20px 0" }}>No issues found.</div>}
                </div>
                <div className="results-layout__aside">
                  <ResultAside result={page.result} animate={false} onLightbox={onLightbox} />
                </div>
              </div>
            ) : page.error ? (
              <div className="alert alert--error" style={{ marginTop: 12 }}>Failed: {page.error}</div>
            ) : (
              <Scanning />
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

// ── Batch results ─────────────────────────────────────────────────────────────
function BatchView({ onLightbox, onAutoFollow }) {
  const { batchHistory, batchActiveRun, setBatchActiveRun, removeBatchRun } = useScanStore();
  const run = batchHistory.find(r => r.runId === batchActiveRun) || batchHistory[0];
  const [activePage, setActivePage] = useState(0);

  function changePage(i) {
    setActivePage(i);
    const url = (run?.results || [])[i]?.url;
    if (url) onAutoFollow?.(url);
  }

  if (!run) return <Scanning />;
  const pages = run.results || [];
  const page = pages[activePage];

  return (
    <>
      <RunPicker runs={batchHistory} activeId={run.runId} onSelect={(id) => { setBatchActiveRun(id); setActivePage(0); }} onRemove={removeBatchRun} />

      <div className="batch-nav">
        {pages.map((p, i) => (
          <motion.button key={i}
            className={`batch-nav__item${activePage === i ? " batch-nav__item--active" : ""}`}
            onClick={() => setActivePage(i)}
            whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}>
            <span>#{i + 1}</span>
            {p.result?.score != null && (
              <span className="batch-nav__item__score" style={{ color: scoreColor(p.result.score) }}>
                {p.result.score}
              </span>
            )}
          </motion.button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {page && (
          <motion.div key={activePage}
            initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -12 }} transition={{ duration: 0.18 }}>

            <div className="batch-page-header">
              <div className="batch-page-header__left">
                <div className="batch-page-header__num">Site {activePage + 1} of {pages.length}</div>
                <div className="batch-page-header__title">{page.result?.title || page.url}</div>
                <a href={page.url} target="_blank" rel="noopener noreferrer" className="batch-page-header__url">
                  {page.url} <ExternalLink size={10} />
                </a>
                {page.result?._tokens && (
                  <div style={{ marginTop: 4 }}>
                    <TokenBadge tokens={page.result._tokens} costType="audit" />
                  </div>
                )}
              </div>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 10 }}>
                {page.result && <ScoreRing score={page.result.score ?? 0} size={88} />}
                {page.url && <EmailButton url={page.url} />}
              </div>
            </div>

            {page.result ? (
              <div className="results-layout">
                <div className="results-layout__main">
                  <IssueList issues={page.result.issues || []} scanResult={page.result} />
                  {!page.result.issues?.length && <div style={{ fontSize: 13, color: "var(--ink3)", padding: "20px 0" }}>No issues found.</div>}
                </div>
                <div className="results-layout__aside">
                  <ResultAside result={page.result} animate={false} onLightbox={onLightbox} />
                </div>
              </div>
            ) : page.error ? (
              <div className="alert alert--error" style={{ marginTop: 12 }}>Failed: {page.error}</div>
            ) : (
              <Scanning />
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

function Scanning() {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      style={{ display: "flex", alignItems: "center", gap: 12, padding: "24px 0", color: "var(--ink3)" }}>
      <div className="spinner" />
      <span style={{ fontSize: 13 }}>Scanning in progress…</span>
    </motion.div>
  );
}

// ── Mode tab strip ────────────────────────────────────────────────────────────
function ModeTabs({ active, onSelect, shallowCount, deepCount, batchCount }) {
  const tabs = [
    { id: "shallow", label: "Single", count: shallowCount },
    { id: "deep", label: "Deep", count: deepCount },
    { id: "batch", label: "Batch", count: batchCount },
  ];
  return (
    <div style={{ display: "flex", gap: 0, marginBottom: 24, borderBottom: "1px solid var(--border)" }}>
      {tabs.map(t => (
        <button key={t.id} onClick={() => onSelect(t.id)}
          style={{
            padding: "9px 18px", fontSize: 13, fontWeight: 500,
            color: active === t.id ? "var(--blue)" : "var(--ink3)",
            borderBottom: active === t.id ? "2px solid var(--blue)" : "2px solid transparent",
            background: "none", marginBottom: "-1px", cursor: "pointer",
            display: "flex", alignItems: "center", gap: 6, transition: "color 0.15s",
          }}>
          {t.label}
          {t.count > 0 && (
            <span style={{
              fontSize: 10, fontFamily: "var(--font-mono)", padding: "1px 5px",
              borderRadius: 99, background: active === t.id ? "var(--blue-glow)" : "var(--surface)",
              color: active === t.id ? "var(--blue)" : "var(--ink3)",
              border: "1px solid var(--border)",
            }}>{t.count}</span>
          )}
        </button>
      ))}
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────
export default function ResultsPage() {
  const store = useScanStore();
  const { toggleOpen } = useAgentStore();
  const { drawerUrl, openDrawerFor } = useEmailStore();
  const [lightbox, setLightbox] = useState(null);
  const [viewMode, setViewMode] = useState(store.activeMode || "shallow");

  const anyResults = store.hasAnyResults();

  // Auto-follow: if email drawer is open and user navigates to a different result,
  // switch drawer to the new result's URL (only if that URL has an email entry)
  function autoFollowEmail(newUrl) {
    if (!drawerUrl || !newUrl || drawerUrl === newUrl) return;
    // Switch to the new URL — even if email not yet generated, it opens the panel ready to generate
    openDrawerFor(newUrl);
  }

  if (!anyResults && store.status !== "scanning") {
    return (
      <div className="content">
        <motion.div className="empty-state"
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <TrendingDown size={48} />
          <h3>No results yet</h3>
          <p>Run a scan from the Scan tab to see audit results here.</p>
        </motion.div>
      </div>
    );
  }

  return (
    <>
      <div className="content">
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>

          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
            <div className="page-heading" style={{ marginBottom: 0 }}>
              <h1>Results</h1>
              {store.status === "scanning" && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--blue)", marginTop: 4 }}>
                  <div className="spinner" /> Scanning in progress…
                </motion.div>
              )}
            </div>
            <button className="btn btn--ghost btn--sm" onClick={toggleOpen}>
              <Bot size={14} /> Agent
            </button>
          </div>

          <ModeTabs
            active={viewMode}
            onSelect={setViewMode}
            shallowCount={store.shallowHistory.length}
            deepCount={store.deepHistory.length}
            batchCount={store.batchHistory.length}
          />

          <AnimatePresence mode="wait">
            <motion.div key={viewMode}
              initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }} transition={{ duration: 0.15 }}>
              {viewMode === "shallow" && <ShallowView onLightbox={(s, u) => setLightbox({ src: s, url: u })} />}
              {viewMode === "deep" && <DeepView onLightbox={(s, u) => setLightbox({ src: s, url: u })} />}
              {viewMode === "batch" && <BatchView onLightbox={(s, u) => setLightbox({ src: s, url: u })} onAutoFollow={autoFollowEmail} />}
            </motion.div>
          </AnimatePresence>

        </motion.div>
      </div>

      {lightbox && <ScreenshotLightbox src={lightbox.src} url={lightbox.url} onClose={() => setLightbox(null)} />}
    </>
  );
}
