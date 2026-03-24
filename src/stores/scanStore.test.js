/* eslint-disable no-unused-vars */
import { describe, it, expect, beforeEach } from "vitest";
import { useScanStore } from "./scanStore.js";

describe("scanStore", () => {
  beforeEach(() => {
    // Reset store to initial state
    useScanStore.setState({
      status: "idle",
      activeMode: "shallow",
      activeScanId: null,
      error: null,
      shallowHistory: [],
      deepHistory: [],
      batchHistory: [],
      shallowActiveRun: null,
      deepActiveRun: null,
      batchActiveRun: null,
      activeTab: "scan",
    });
  });

  describe("shallow scan", () => {
    it("should start a shallow scan and add to history", () => {
      const runId = useScanStore.getState().startShallow("https://example.com");
      expect(runId).toMatch(/^run-\d+-\d+$/);

      const state = useScanStore.getState();
      expect(state.status).toBe("scanning");
      expect(state.activeScanId).toBe(runId);
      expect(state.shallowHistory).toHaveLength(1);
      expect(state.shallowHistory[0].url).toBe("https://example.com");
      expect(state.shallowHistory[0].result).toBeNull();
    });

    it("should finish a shallow scan and update result", () => {
      const runId = useScanStore.getState().startShallow("https://example.com");
      const result = { score: 85, issues: [] };

      useScanStore.getState().finishShallow(runId, result);

      const state = useScanStore.getState();
      expect(state.status).toBe("done");
      expect(state.activeScanId).toBeNull();
      expect(state.shallowHistory[0].result).toEqual(result);
      expect(state.activeTab).toBe("results");
    });

    it("should finish shallow silently without switching tab", () => {
      const runId = useScanStore.getState().startShallow("https://example.com");
      useScanStore.setState({ activeTab: "discover" });
      const result = { score: 85, issues: [] };

      useScanStore.getState().finishShallowSilent(runId, result);

      const state = useScanStore.getState();
      expect(state.status).toBe("done");
      expect(state.activeTab).toBe("discover");
    });

    it("should remove a shallow run from history", () => {
      const runId1 = useScanStore.getState().startShallow("https://example1.com");
      const runId2 = useScanStore.getState().startShallow("https://example2.com");

      expect(useScanStore.getState().shallowHistory).toHaveLength(2);

      useScanStore.getState().removeShallowRun(runId1);

      const state = useScanStore.getState();
      expect(state.shallowHistory).toHaveLength(1);
      // runId2 was added last (unshift), so it's first in the array
      expect(state.shallowHistory[0].url).toBe("https://example2.com");
      expect(state.shallowActiveRun).toBe(runId2);
    });

    it("should update shallowActiveRun when removing active run", () => {
      const runId1 = useScanStore.getState().startShallow("https://example1.com");
      const runId2 = useScanStore.getState().startShallow("https://example2.com");
      useScanStore.getState().setShallowActiveRun(runId1);

      useScanStore.getState().removeShallowRun(runId1);

      const state = useScanStore.getState();
      expect(state.shallowActiveRun).toBe(runId2);
    });
  });

  describe("deep scan", () => {
    it("should start a deep scan with progress tracking", () => {
      const runId = useScanStore.getState().startDeep("https://example.com", 20);

      const state = useScanStore.getState();
      expect(state.status).toBe("scanning");
      expect(state.deepHistory[0].url).toBe("https://example.com");
      expect(state.deepHistory[0].pages).toEqual([]);
      expect(state.deepHistory[0].progress).toEqual({ current: 0, total: 20 });
    });

    it("should add pages to deep scan and calculate average score", () => {
      const runId = useScanStore.getState().startDeep("https://example.com", 3);

      useScanStore.getState().addDeepPage(runId, { url: "/page1", result: { score: 80 } });
      useScanStore.getState().addDeepPage(runId, { url: "/page2", result: { score: 90 } });

      const state = useScanStore.getState();
      expect(state.deepHistory[0].pages).toHaveLength(2);
      expect(state.deepHistory[0].overallScore).toBe(85);
      expect(state.deepHistory[0].progress.current).toBe(2);
    });

    it("should handle null scores in average calculation", () => {
      const runId = useScanStore.getState().startDeep("https://example.com", 3);

      useScanStore.getState().addDeepPage(runId, { url: "/page1", result: { score: 80 } });
      useScanStore.getState().addDeepPage(runId, { url: "/page2", result: null });

      const state = useScanStore.getState();
      expect(state.deepHistory[0].overallScore).toBe(80);
    });

    it("should set deep total pages", () => {
      const runId = useScanStore.getState().startDeep("https://example.com", 5);
      useScanStore.getState().setDeepTotal(runId, 10);

      expect(useScanStore.getState().deepHistory[0].progress.total).toBe(10);
    });
  });

  describe("batch scan", () => {
    it("should start a batch scan with multiple URLs", () => {
      const urls = ["https://a.com", "https://b.com", "https://c.com"];
      const runId = useScanStore.getState().startBatch(urls);

      const state = useScanStore.getState();
      expect(state.status).toBe("scanning");
      expect(state.batchHistory[0].urls).toEqual(urls);
      expect(state.batchHistory[0].progress).toEqual({ current: 0, total: 3 });
    });

    it("should add batch results", () => {
      const urls = ["https://a.com", "https://b.com"];
      const runId = useScanStore.getState().startBatch(urls);

      useScanStore.getState().addBatchResult(runId, { url: "https://a.com", score: 75 });
      useScanStore.getState().addBatchResult(runId, { url: "https://b.com", score: 85 });

      const state = useScanStore.getState();
      expect(state.batchHistory[0].results).toHaveLength(2);
      expect(state.batchHistory[0].progress.current).toBe(2);
    });
  });

  describe("selectors", () => {
    it("should get run by ID", () => {
      const runId = useScanStore.getState().startShallow("https://example.com");
      const run = useScanStore.getState().getShallowRun(runId);
      expect(run.url).toBe("https://example.com");
    });

    it("should return first run if ID not found", () => {
      useScanStore.getState().startShallow("https://example.com");
      const run = useScanStore.getState().getShallowRun("nonexistent");
      expect(run.url).toBe("https://example.com");
    });

    it("should check if any results exist", () => {
      expect(useScanStore.getState().hasAnyResults()).toBe(false);
      useScanStore.getState().startShallow("https://example.com");
      expect(useScanStore.getState().hasAnyResults()).toBe(true);
    });

    it("should get latest run per mode", () => {
      useScanStore.getState().startShallow("https://first.com");
      useScanStore.getState().startShallow("https://second.com");

      const latest = useScanStore.getState().latestShallow();
      expect(latest.url).toBe("https://second.com");
    });
  });

  describe("error handling", () => {
    it("should set scan error", () => {
      useScanStore.getState().startShallow("https://example.com");
      useScanStore.getState().setScanError("Network timeout");

      const state = useScanStore.getState();
      expect(state.status).toBe("error");
      expect(state.error).toBe("Network timeout");
      expect(state.activeScanId).toBeNull();
    });

    it("should cancel scan", () => {
      useScanStore.getState().startShallow("https://example.com");
      useScanStore.getState().cancelScan();

      const state = useScanStore.getState();
      expect(state.status).toBe("idle");
      expect(state.activeScanId).toBeNull();
    });
  });

  describe("mode selection", () => {
    it("should set active mode", () => {
      useScanStore.getState().setMode("deep");
      expect(useScanStore.getState().activeMode).toBe("deep");
    });

    it("should set active tab", () => {
      useScanStore.getState().setActiveTab("history");
      expect(useScanStore.getState().activeTab).toBe("history");
    });
  });
});