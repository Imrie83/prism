import { useState, useRef } from "react";
import { Search, Layers, List, Play, Square, AlertCircle, Mail } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useScanStore } from "../stores/scanStore";
import { useEmailStore } from "../stores/emailStore";
import { useSettingsStore } from "../stores/settingsStore";
import { useAgentStore } from "../stores/agentStore";
import { api } from "../lib/api";

const MODES = [
  { id: "shallow", label: "Shallow", icon: Search, desc: "Single page — full results + email generation" },
  { id: "deep",    label: "Deep",    icon: Layers, desc: "Crawl all subpages — per-page + overall score" },
  { id: "batch",   label: "Batch",   icon: List,   desc: "Multiple URLs — shallow scan each" },
];

const MAX_RETRIES = 3;
let _taskSeq = 0;
function makeTaskId(prefix) { return `${prefix}-${Date.now()}-${++_taskSeq}`; }

export default function ScanPage() {
  const store = useScanStore();
  const settings = useSettingsStore();
  const agentStore = useAgentStore();
  const emailStore = useEmailStore();

  const activeTaskIds = useRef(new Set());
  const abortRef = useRef(null);
  const cancelledRef = useRef(false);

  const [localUrl, setLocalUrl] = useState("");
  const [batchText, setBatchText] = useState("");
  const [localScanning, setLocalScanning] = useState(false);
  const [historyBanner, setHistoryBanner] = useState(null);

  const isScanning = store.status === "scanning" || localScanning;

  function getSettings() {
    return {
      ai_provider: settings.aiProvider,
      ollama_base_url: settings.ollamaBaseUrl,
      ollama_model: settings.ollamaModel,
      openai_api_key: settings.openaiApiKey,
      openai_model: settings.openaiModel,
      anthropic_api_key: settings.anthropicApiKey,
      anthropic_model: settings.anthropicModel,
      screenshot_service_url: settings.screenshotServiceUrl,
      max_deep_pages: settings.maxDeepPages,
    };
  }

  function getEmailAISettings() {
    const provider = settings.emailAiProvider || settings.aiProvider;
    return {
      ai_provider:       provider,
      ollama_base_url:   settings.ollamaBaseUrl,
      ollama_model:      provider === "ollama" ? (settings.emailOllamaModel || settings.ollamaModel) : settings.ollamaModel,
      openai_api_key:    settings.openaiApiKey,
      openai_model:      provider === "openai" ? (settings.emailOpenaiModel || settings.openaiModel) : settings.openaiModel,
      anthropic_api_key: settings.anthropicApiKey,
      anthropic_model:   provider === "claude" ? (settings.emailAnthropicModel || settings.anthropicModel) : settings.anthropicModel,
      your_name:    settings.yourName,
      your_title:   settings.yourTitle,
      your_email:   settings.yourEmail,
      your_website: settings.yourWebsite,
    };
  }

  // After a scan completes, optionally extract found emails + auto-generate email
  function handleScanResult(url, result) {
    // Auto-populate recipient if emails were found in the page HTML,
    // otherwise fall back to info@<domain>
    const existing = emailStore.getEmail(url);
    if (!existing?.recipientEmail) {
      let recipient = result.emails_found?.[0];
      if (!recipient) {
        try {
          const domain = new URL(url).hostname.replace(/^www\./, "");
          recipient = `info@${domain}`;
        } catch {}
      }
      if (recipient) emailStore.setRecipient(url, recipient);
    }
    // Auto-generate email draft if toggle is on
    if (settings.autoGenerateEmail) {
      emailStore.generate(url, result, getEmailAISettings());
    }
  }

  async function cancelAll() {
    cancelledRef.current = true;
    abortRef.current?.abort();
    for (const taskId of activeTaskIds.current) {
      api.cancelTask(taskId);
    }
    activeTaskIds.current.clear();
    setLocalScanning(false);
    store.cancelScan();
  }

  // Retry wrapper: attempts fn up to MAX_RETRIES times on non-abort errors
  async function withRetry(fn, label) {
    let lastErr;
    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
      if (cancelledRef.current || abortRef.current?.signal.aborted) throw new Error("cancelled");
      try {
        return await fn();
      } catch (e) {
        if (e.message === "cancelled" || e.name === "AbortError") throw e;
        lastErr = e;
        console.warn(`[retry] ${label} attempt ${attempt}/${MAX_RETRIES} failed: ${e.message}`);
        if (attempt < MAX_RETRIES) {
          await new Promise(r => setTimeout(r, 1500 * attempt)); // backoff
        }
      }
    }
    throw lastErr;
  }

  async function runShallow() {
    const url = localUrl.trim();
    if (!url || isScanning) return;
    cancelledRef.current = false;
    setLocalScanning(true);
    agentStore.clearHistory();
    abortRef.current = new AbortController();
    const taskId = makeTaskId("shallow");
    activeTaskIds.current.add(taskId);
    const runId = store.startShallow(url);
    try {
      const result = await withRetry(
        () => api.analyzePage(url, getSettings(), taskId, abortRef.current.signal, "shallow"),
        `shallow ${url}`
      );
      store.finishShallow(runId, result);
      handleScanResult(url, result);
    } catch (e) {
      if (e.message === "cancelled" || e.name === "AbortError") { store.cancelScan(); }
      else { store.setScanError(`Failed after ${MAX_RETRIES} attempts: ${e.message}`); }
    } finally {
      activeTaskIds.current.delete(taskId);
      setLocalScanning(false);
    }
  }

  async function runDeep() {
    const url = localUrl.trim();
    if (!url || isScanning) return;
    cancelledRef.current = false;
    setLocalScanning(true);
    agentStore.clearHistory();
    abortRef.current = new AbortController();

    // Step 1: crawl for URLs (no retry — fast operation)
    let urls = [];
    try {
      const crawlTaskId = makeTaskId("crawl");
      activeTaskIds.current.add(crawlTaskId);
      const { urls: crawled } = await api.crawl(url, settings.maxDeepPages, abortRef.current.signal);
      activeTaskIds.current.delete(crawlTaskId);
      urls = crawled;
    } catch (e) {
      setLocalScanning(false);
      if (e.message === "cancelled" || e.name === "AbortError") { store.cancelScan(); return; }
      store.setScanError(`Crawl failed: ${e.message}`);
      return;
    }

    const runId = store.startDeep(url, urls.length);
    setLocalScanning(false); // store.status now = "scanning" — local flag no longer needed

    let consecutiveFails = 0;
    for (const pageUrl of urls) {
      if (cancelledRef.current || abortRef.current?.signal.aborted) break;
      const taskId = makeTaskId("deep-page");
      activeTaskIds.current.add(taskId);
      try {
        const result = await withRetry(
          () => api.analyzePage(pageUrl, getSettings(), taskId, abortRef.current.signal, "deep"),
          `deep ${pageUrl}`
        );
        store.addDeepPage(runId, { url: pageUrl, title: result.title || pageUrl, result });
        consecutiveFails = 0;
      } catch (e) {
        if (e.message === "cancelled" || e.name === "AbortError") break;
        consecutiveFails++;
        console.error(`[deep] page failed: ${pageUrl} (${consecutiveFails} consecutive)`);
        store.addDeepPage(runId, { url: pageUrl, title: pageUrl, result: null, error: e.message });
        // Stop after 3 consecutive failures — service is probably down
        if (consecutiveFails >= MAX_RETRIES) {
          store.setScanError(`Stopped: ${MAX_RETRIES} consecutive page failures. Check AI/screenshot service.`);
          break;
        }
      } finally {
        activeTaskIds.current.delete(taskId);
      }
    }
    store.finishDeep(runId);
  }

  async function runBatch() {
    const urls = batchText.split("\n").map(u => u.trim()).filter(Boolean);
    if (!urls.length || isScanning) return;
    cancelledRef.current = false;
    setLocalScanning(true);
    agentStore.clearHistory();
    abortRef.current = new AbortController();
    const runId = store.startBatch(urls);
    setLocalScanning(false);

    let consecutiveFails = 0;
    for (const url of urls) {
      if (cancelledRef.current || abortRef.current?.signal.aborted) break;
      const taskId = makeTaskId("batch-page");
      activeTaskIds.current.add(taskId);
      try {
        const result = await withRetry(
          () => api.analyzePage(url, getSettings(), taskId, abortRef.current.signal, "batch"),
          `batch ${url}`
        );
        store.addBatchResult(runId, { url, result });
        handleScanResult(url, result);
        consecutiveFails = 0;
      } catch (e) {
        if (e.message === "cancelled" || e.name === "AbortError") break;
        consecutiveFails++;
        store.addBatchResult(runId, { url, result: null, error: e.message });
        if (consecutiveFails >= MAX_RETRIES) {
          store.setScanError(`Stopped: ${MAX_RETRIES} consecutive failures. Check services.`);
          break;
        }
      } finally {
        activeTaskIds.current.delete(taskId);
      }
    }
    store.finishBatch(runId);
  }

  async function handleRun() {
    if (isScanning) return;
    const url = localUrl.trim();

    // Always check history before scanning (shallow/deep only — batch handles its own)
    if (store.activeMode !== "batch" && url) {
      try {
        const check = await api.checkHistory(url);
        if (check.exists) {
          setHistoryBanner(check);
          return; // stop — user must choose from the banner
        }
      } catch {} // ignore network errors — proceed with scan
    }

    setHistoryBanner(null);
    if (store.activeMode === "shallow") return runShallow();
    if (store.activeMode === "deep")    return runDeep();
    if (store.activeMode === "batch")   return runBatch();
  }

  function handleScanAnyway() {
    setHistoryBanner(null);
    if (store.activeMode === "shallow") runShallow();
    else if (store.activeMode === "deep") runDeep();
  }

  const activeRun = (() => {
    if (store.activeMode === "deep"  && store.deepHistory[0]?.status === "scanning")  return store.deepHistory[0];
    if (store.activeMode === "batch" && store.batchHistory[0]?.status === "scanning") return store.batchHistory[0];
    return null;
  })();
  const progress = activeRun?.progress || { current: 0, total: 0 };
  const pct = progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0;

  return (
    <div className="content">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>

        <div className="mb-24">
          <h1 style={{ fontSize: 22, fontWeight: 800, marginBottom: 6, letterSpacing: "-0.4px" }}>New Audit</h1>
          <p className="text-muted text-sm">Scan a Japanese website for English localisation and UX issues.</p>
        </div>

        {/* Mode selector */}
        <div className="mb-24">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
            {MODES.map(({ id, label, icon: Icon, desc }) => (
              <motion.button key={id}
                onClick={() => !isScanning && store.setMode(id)}
                whileHover={!isScanning ? { scale: 1.02 } : {}}
                whileTap={!isScanning ? { scale: 0.98 } : {}}
                style={{
                  padding: "16px 18px",
                  background: store.activeMode === id ? "var(--blue-glow)" : "var(--surface)",
                  border: `1px solid ${store.activeMode === id ? "var(--blue-line)" : "var(--border)"}`,
                  borderRadius: "var(--radius-lg)", textAlign: "left",
                  cursor: isScanning ? "not-allowed" : "pointer", transition: "all 0.15s",
                  boxShadow: store.activeMode === id ? "var(--glow-blue)" : "none",
                }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <Icon size={15} color={store.activeMode === id ? "var(--blue)" : "var(--ink3)"} />
                  <span style={{ fontWeight: 700, fontSize: 13, color: store.activeMode === id ? "var(--blue)" : "var(--ink)" }}>{label}</span>
                </div>
                <p style={{ fontSize: 11, color: "var(--ink3)", lineHeight: 1.5 }}>{desc}</p>
              </motion.button>
            ))}
          </div>
        </div>

        {/* URL input */}
        {store.activeMode !== "batch" && (
          <div className="panel mb-24">
            <div className="panel-header"><h2>Target URL</h2></div>
            <div className="panel-body">
              <div className="url-bar">
                <input type="url" value={localUrl}
                  onChange={e => setLocalUrl(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && !isScanning && handleRun()}
                  placeholder="https://example.co.jp"
                  disabled={isScanning} />
                {isScanning
                  ? <button className="btn btn--danger" onClick={cancelAll}><Square size={14} /> Stop</button>
                  : <button className="btn btn--primary" onClick={handleRun} disabled={!localUrl.trim() || isScanning}>
                      <Play size={14} /> Scan
                    </button>}
              </div>
              {/* Auto-generate email toggle */}
              <div style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Mail size={13} color="var(--ink3)" />
                  <span style={{ fontSize: 12, color: "var(--ink2)", fontWeight: 500 }}>Auto-generate email after scan</span>
                </div>
                <button
                  onClick={() => settings.setField("autoGenerateEmail", !settings.autoGenerateEmail)}
                  disabled={isScanning}
                  style={{
                    width: 36, height: 20, borderRadius: 10, border: "none", cursor: isScanning ? "not-allowed" : "pointer",
                    background: settings.autoGenerateEmail ? "var(--blue)" : "var(--border)",
                    position: "relative", transition: "background 0.2s", flexShrink: 0,
                  }}>
                  <span style={{
                    position: "absolute", top: 2, left: settings.autoGenerateEmail ? 18 : 2,
                    width: 16, height: 16, borderRadius: "50%", background: "white",
                    transition: "left 0.2s", boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                  }} />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* History banner — shown when URL has been scanned before */}
        <AnimatePresence>
          {historyBanner && (
            <motion.div
              initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
              style={{
                marginBottom: 16, padding: "14px 18px",
                background: "var(--blue-glow)", border: "1px solid var(--blue-line)",
                borderRadius: "var(--radius-lg)", display: "flex", alignItems: "flex-start", gap: 12,
              }}>
              <AlertCircle size={16} style={{ color: "var(--blue)", flexShrink: 0, marginTop: 1 }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 13, color: "var(--ink1)", marginBottom: 3 }}>
                  Already scanned{historyBanner.title ? ` — ${historyBanner.title}` : ""}
                </div>
                <div style={{ fontSize: 12, color: "var(--ink2)", marginBottom: 10 }}>
                  Score: <strong>{historyBanner.score}/100</strong>
                  {" · "}Scanned {new Date(historyBanner.scanned_at).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}
                  {historyBanner.email?.sent_at && (
                    <> · <span style={{ color: "var(--green)" }}>
                      Email sent to {historyBanner.email.recipient} on {new Date(historyBanner.email.sent_at).toLocaleDateString("en-GB", { day: "2-digit", month: "short" })}
                    </span></>
                  )}
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="btn btn--sm btn--ghost"
                    onClick={() => { store.setActiveTab("history"); setHistoryBanner(null); }}>
                    View in History
                  </button>
                  <button className="btn btn--sm btn--primary" onClick={handleScanAnyway}>
                    Scan Again
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Batch URL list */}
        {store.activeMode === "batch" && (
          <div className="panel mb-24">
            <div className="panel-header">
              <h2>URL List</h2>
              <span className="text-muted text-xs text-mono">one URL per line</span>
            </div>
            <div className="panel-body">
              <textarea value={batchText} onChange={e => setBatchText(e.target.value)}
                placeholder={"https://company-a.co.jp\nhttps://company-b.co.jp\nhttps://company-c.co.jp"}
                rows={8} disabled={isScanning}
                style={{ width: "100%", fontFamily: "var(--font-mono)", fontSize: 12, resize: "vertical" }} />
              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12, gap: 8 }}>
                {isScanning
                  ? <button className="btn btn--danger" onClick={cancelAll}><Square size={14} /> Stop Batch</button>
                  : <button className="btn btn--primary btn--lg" onClick={runBatch} disabled={!batchText.trim() || isScanning}>
                      <Play size={14} /> Start Batch
                    </button>}
              </div>
            </div>
          </div>
        )}

        {/* Progress — shown immediately even before page count is known */}
        <AnimatePresence>
          {isScanning && (store.activeMode === "deep" || store.activeMode === "batch") && (
            <motion.div key="progress"
              initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
              className="panel mb-24">
              <div className="panel-header">
                <h2>Scanning…</h2>
                <span style={{ fontSize: 11, color: "var(--blue)", fontFamily: "var(--font-mono)" }}>
                  {activeRun && progress.total > 0 ? `${pct}%` : "starting…"}
                </span>
              </div>
              <div className="panel-body">
                <div className="scan-progress">
                  <div className="scan-progress__label">
                    <span>{store.activeMode === "deep" ? "Analysing pages" : "Processing URLs"}</span>
                    <span>{activeRun ? `${progress.current} / ${progress.total || "?"}` : "Crawling…"}</span>
                  </div>
                  <div className="progress-bar">
                    {activeRun && progress.total > 0
                      ? <div className="progress-bar__fill" style={{ width: `${pct}%` }} />
                      : <div className="progress-bar__fill progress-bar__fill--indeterminate" />
                    }
                  </div>
                  {activeRun && (store.activeMode === "deep") && activeRun.pages?.length > 0 && (
                    <div style={{ fontSize: 11, color: "var(--ink3)", fontFamily: "var(--font-mono)", marginTop: 4 }}>
                      Last: {activeRun.pages[activeRun.pages.length - 1]?.url}
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}

          {isScanning && store.activeMode === "shallow" && (
            <motion.div key="shallow-spinner"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="panel" style={{ padding: 32, display: "flex", alignItems: "center", gap: 16 }}>
              <div className="spinner" style={{ width: 24, height: 24, borderWidth: 3 }} />
              <div>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>Analysing page…</div>
                <div className="text-muted text-sm">Screenshot + AI audit in progress</div>
              </div>
              <button className="btn btn--danger btn--sm" onClick={cancelAll} style={{ marginLeft: "auto" }}>
                <Square size={12} /> Stop
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Error */}
        <AnimatePresence>
          {store.status === "error" && store.error && (
            <motion.div key="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              style={{
                display: "flex", alignItems: "center", gap: 12, padding: "14px 18px",
                background: "rgba(248,113,113,0.08)", border: "1px solid rgba(248,113,113,0.3)",
                borderRadius: "var(--radius)", color: "var(--red)",
              }}>
              <AlertCircle size={16} />
              <span style={{ fontSize: 13 }}>{store.error}</span>
            </motion.div>
          )}
        </AnimatePresence>

      </motion.div>
    </div>
  );
}
