import { create } from "zustand";

/*
 * Prism scan store — v0.4.0
 *
 * History model: each scan type keeps an independent list of past runs.
 * Switching mode never clears results. Each run has a unique runId.
 *
 * shallowHistory: [{ runId, url, result, ts }]
 * deepHistory:    [{ runId, url, pages[], overallScore, progress, status, ts }]
 * batchHistory:   [{ runId, urls[], results[], progress, status, ts }]
 *
 * activeRunId per mode tracks which run is shown in Results.
 * status / activeMode reflect the currently *running* scan.
 */

let nextId = 1;
function genId() { return `run-${Date.now()}-${nextId++}`; }
function avgScore(pages) {
  const scores = pages.map(p => p.result?.score).filter(s => s != null);
  return scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null;
}

export const useScanStore = create((set, get) => ({
  // Active scan state
  status: "idle", // "idle" | "scanning" | "done" | "error"
  activeMode: "shallow", // current UI mode selector
  activeScanId: null, // runId currently scanning
  error: null,

  // History banks
  shallowHistory: [],
  deepHistory: [],
  batchHistory: [],

  // Active tab in results view per mode
  shallowActiveRun: null,
  deepActiveRun: null,
  batchActiveRun: null,

  // UI tab
  activeTab: "scan",

  // ── Selectors ──────────────────────────────────────────────────
  getShallowRun: (id) => get().shallowHistory.find(r => r.runId === id) || get().shallowHistory[0] || null,
  getDeepRun: (id) => get().deepHistory.find(r => r.runId === id) || get().deepHistory[0] || null,
  getBatchRun: (id) => get().batchHistory.find(r => r.runId === id) || get().batchHistory[0] || null,

  // Latest run per mode (for Results page default view)
  latestShallow: () => get().shallowHistory[0] || null,
  latestDeep: () => get().deepHistory[0] || null,
  latestBatch: () => get().batchHistory[0] || null,

  hasAnyResults: () => {
    const s = get();
    return s.shallowHistory.length > 0 || s.deepHistory.length > 0 || s.batchHistory.length > 0;
  },

  // ── Mode selector ───────────────────────────────────────────────
  setMode: (mode) => set({ activeMode: mode }),
  setActiveTab: (tab) => set({ activeTab: tab }),

  // ── Shallow scan ────────────────────────────────────────────────
  startShallow: (url) => {
    const runId = genId();
    set(s => ({
      status: "scanning",
      activeScanId: runId,
      error: null,
      shallowHistory: [{ runId, url, result: null, ts: Date.now() }, ...s.shallowHistory],
      shallowActiveRun: runId,
    }));
    return runId;
  },

  finishShallow: (runId, result) => set(s => ({
    status: "done",
    activeScanId: null,
    shallowHistory: s.shallowHistory.map(r =>
      r.runId === runId ? { ...r, result } : r
    ),
    shallowActiveRun: runId,
    activeTab: "results",
  })),

  // Like finishShallow but does NOT switch the active tab — used when scanning
  // is triggered from a page other than Scan (e.g. Discover)
  finishShallowSilent: (runId, result) => set(s => ({
    status: "done",
    activeScanId: null,
    shallowHistory: s.shallowHistory.map(r =>
      r.runId === runId ? { ...r, result } : r
    ),
    shallowActiveRun: runId,
  })),

  // ── Deep scan ───────────────────────────────────────────────────
  startDeep: (url, total) => {
    const runId = genId();
    set(s => ({
      status: "scanning",
      activeScanId: runId,
      error: null,
      deepHistory: [{
        runId, url, pages: [], overallScore: null,
        progress: { current: 0, total },
        status: "scanning", ts: Date.now(),
      }, ...s.deepHistory],
      deepActiveRun: runId,
    }));
    return runId;
  },

  addDeepPage: (runId, page) => set(s => ({
    deepHistory: s.deepHistory.map(r => {
      if (r.runId !== runId) return r;
      const pages = [...r.pages, page];
      return {
        ...r,
        pages,
        overallScore: avgScore(pages),
        progress: { ...r.progress, current: pages.length },
      };
    }),
  })),

  setDeepTotal: (runId, total) => set(s => ({
    deepHistory: s.deepHistory.map(r =>
      r.runId === runId ? { ...r, progress: { ...r.progress, total } } : r
    ),
  })),

  finishDeep: (runId) => set(s => ({
    status: "done",
    activeScanId: null,
    deepActiveRun: runId,
    activeTab: "results",
    deepHistory: s.deepHistory.map(r =>
      r.runId === runId ? { ...r, status: "done" } : r
    ),
  })),

  // ── Batch scan ──────────────────────────────────────────────────
  startBatch: (urls) => {
    const runId = genId();
    set(s => ({
      status: "scanning",
      activeScanId: runId,
      error: null,
      batchHistory: [{
        runId, urls, results: [],
        progress: { current: 0, total: urls.length },
        status: "scanning", ts: Date.now(),
      }, ...s.batchHistory],
      batchActiveRun: runId,
    }));
    return runId;
  },

  addBatchResult: (runId, item) => set(s => ({
    batchHistory: s.batchHistory.map(r => {
      if (r.runId !== runId) return r;
      const results = [...r.results, item];
      return { ...r, results, progress: { ...r.progress, current: results.length } };
    }),
  })),

  finishBatch: (runId) => set(s => ({
    status: "done",
    activeScanId: null,
    batchActiveRun: runId,
    activeTab: "results",
    batchHistory: s.batchHistory.map(r =>
      r.runId === runId ? { ...r, status: "done" } : r
    ),
  })),

  // ── Error / cancel ──────────────────────────────────────────────
  setScanError: (msg) => set({ status: "error", activeScanId: null, error: msg }),
  cancelScan: () => set({ status: "idle", activeScanId: null }),

  // Set active displayed run per mode
  setShallowActiveRun: (id) => set({ shallowActiveRun: id }),
  setDeepActiveRun: (id) => set({ deepActiveRun: id }),
  setBatchActiveRun: (id) => set({ batchActiveRun: id }),

  // Remove a run from history
  removeShallowRun: (id) => set(s => {
    const history = s.shallowHistory.filter(r => r.runId !== id);
    const activeRun = s.shallowActiveRun === id ? (history[0]?.runId || null) : s.shallowActiveRun;
    return { shallowHistory: history, shallowActiveRun: activeRun };
  }),
  removeDeepRun: (id) => set(s => {
    const history = s.deepHistory.filter(r => r.runId !== id);
    const activeRun = s.deepActiveRun === id ? (history[0]?.runId || null) : s.deepActiveRun;
    return { deepHistory: history, deepActiveRun: activeRun };
  }),
  removeBatchRun: (id) => set(s => {
    const history = s.batchHistory.filter(r => r.runId !== id);
    const activeRun = s.batchActiveRun === id ? (history[0]?.runId || null) : s.batchActiveRun;
    return { batchHistory: history, batchActiveRun: activeRun };
  }),
}));
