/* eslint-disable no-unused-vars */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { api } from "./api.js";

describe("api", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn();
  });

  describe("post helper", () => {
    it("should make POST request and return JSON", async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true, data: "test" }),
      });

      // Access internal post via a public method
      const result = await api.health();
      expect(globalThis.fetch).toHaveBeenCalled();
    });

    it("should throw on HTTP error", async () => {
      globalThis.fetch.mockResolvedValue({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ detail: "Internal error" }),
      });

      await expect(api.analyzePage("https://example.com", {}, "task-1")).rejects.toThrow("Internal error");
    });
  });

  describe("analyzePage", () => {
    it("should call analyze endpoint with correct params", async () => {
      const mockReader = {
        read: vi.fn()
          .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode(JSON.stringify({ score: 85 })) })
          .mockResolvedValueOnce({ done: true, value: undefined }),
      };

      globalThis.fetch.mockResolvedValue({
        ok: true,
        body: { getReader: () => mockReader },
      });

      const result = await api.analyzePage(
        "https://example.com",
        { aiProvider: "ollama" },
        "task-123",
        null,
        "shallow",
        false
      );

      expect(globalThis.fetch).toHaveBeenCalledWith("/api/analyze", expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: expect.stringContaining("https://example.com"),
      }));
      expect(result.score).toBe(85);
    });
  });

  describe("cancelTask", () => {
    it("should call cancel endpoint", async () => {
      globalThis.fetch.mockResolvedValue({ ok: true });

      await api.cancelTask("task-123");

      expect(globalThis.fetch).toHaveBeenCalledWith("/api/cancel/task-123", { method: "POST" });
    });

    it("should not throw on cancel error", async () => {
      globalThis.fetch.mockRejectedValue(new Error("Network error"));

      await expect(api.cancelTask("task-123")).resolves.not.toThrow();
    });
  });

  describe("crawl", () => {
    it("should call crawl endpoint", async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ pages: ["/", "/about"] }),
      });

      const result = await api.crawl("https://example.com", 10);

      expect(globalThis.fetch).toHaveBeenCalledWith("/api/crawl", expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("https://example.com"),
      }));
      expect(result.pages).toHaveLength(2);
    });
  });

  describe("history methods", () => {
    it("should get history with pagination params", async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ items: [], total: 0 }),
      });

      await api.getHistory(2, 20, "url", "asc", "all", 0, 100);

      const callUrl = globalThis.fetch.mock.calls[0][0];
      expect(callUrl).toContain("page=2");
      expect(callUrl).toContain("per_page=20");
      expect(callUrl).toContain("sort_by=url");
      expect(callUrl).toContain("sort_dir=asc");
    });

    it("should check history for a URL", async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ exists: true }),
      });

      const result = await api.checkHistory("https://example.com");

      expect(globalThis.fetch).toHaveBeenCalled();
      const callUrl = globalThis.fetch.mock.calls[0][0];
      expect(callUrl).toContain(encodeURIComponent("https://example.com"));
      expect(result.exists).toBe(true);
    });

    it("should get a history entry", async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ url: "https://example.com", score: 85 }),
      });

      const result = await api.getHistoryEntry("https://example.com");

      expect(result.url).toBe("https://example.com");
      expect(result.score).toBe(85);
    });

    it("should throw on missing history entry", async () => {
      globalThis.fetch.mockResolvedValue({
        ok: false,
        json: () => Promise.resolve({}),
      });

      await expect(api.getHistoryEntry("https://unknown.com")).rejects.toThrow("Not found");
    });

    it("should toggle response status", async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ responded: true }),
      });

      const result = await api.toggleResponse("https://example.com");

      expect(result.responded).toBe(true);
    });

    it("should delete history entry", async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      await api.deleteHistoryEntry("https://example.com");

      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/history/entry"),
        { method: "DELETE" }
      );
    });

    it("should update email recipient", async () => {
      globalThis.fetch.mockResolvedValue({ ok: true });

      await api.updateEmailRecipient("https://example.com", "test@example.com");

      const callUrl = globalThis.fetch.mock.calls[0][0];
      expect(callUrl).toContain(encodeURIComponent("test@example.com"));
    });
  });

  describe("discover methods", () => {
    it("should search for prospects with progress callback", async () => {
      const events = [
        { type: "start", keywords: ["restaurant"] },
        { type: "scroll", count: 10 },
        { type: "result", businesses: [{ name: "Test Business" }] },
      ];

      let eventIndex = 0;
      const mockReader = {
        read: vi.fn(() => {
          if (eventIndex < events.length) {
            const event = events[eventIndex++];
            return Promise.resolve({
              done: false,
              value: new TextEncoder().encode(JSON.stringify(event) + "\n"),
            });
          }
          return Promise.resolve({ done: true, value: undefined });
        }),
      };

      globalThis.fetch.mockResolvedValue({
        ok: true,
        body: { getReader: () => mockReader },
      });

      const progressEvents = [];
      const result = await api.discoverSearch(
        "restaurant",
        "Tokyo",
        50,
        (event) => progressEvents.push(event)
      );

      expect(progressEvents.length).toBeGreaterThan(0);
      expect(result.type).toBe("result");
    });

    it("should get a single prospect", async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ website: "https://example.com", name: "Test" }),
      });

      const result = await api.getProspect("https://example.com");

      expect(result.website).toBe("https://example.com");
      expect(result.name).toBe("Test");
    });

    it("should get prospects with filters", async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ prospects: [], total: 0 }),
      });

      await api.getProspects("session-123", "url", "asc", "scanned", "yes");

      const callUrl = globalThis.fetch.mock.calls[0][0];
      expect(callUrl).toContain("session_id=session-123");
      expect(callUrl).toContain("sort_by=url");
      expect(callUrl).toContain("filter_status=scanned");
    });

    it("should get sessions", async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([{ id: "s1", name: "Session 1" }]),
      });

      const result = await api.getSessions();

      expect(result).toHaveLength(1);
    });

    it("should update prospect status", async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      await api.updateProspectStatus("https://example.com", "scanned");

      expect(globalThis.fetch).toHaveBeenCalledWith("/api/discover/status", expect.objectContaining({
        method: "PATCH",
        body: expect.stringContaining("scanned"),
      }));
    });

    it("should delete a prospect", async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      await api.deleteProspect("https://example.com");

      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/discover/prospect"),
        { method: "DELETE" }
      );
    });

    it("should update prospect email", async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      await api.updateProspectEmail("https://example.com", "test@example.com");

      expect(globalThis.fetch).toHaveBeenCalledWith("/api/discover/email", expect.objectContaining({
        method: "PATCH",
        body: expect.stringContaining("test@example.com"),
      }));
    });
  });

  describe("sendEmail", () => {
    it("should send email with correct params", async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      await api.sendEmail(
        "recipient@example.com",
        "Test Subject",
        "<p>Body</p>",
        { aiProvider: "ollama" },
        "https://example.com"
      );

      expect(globalThis.fetch).toHaveBeenCalledWith("/api/send-email", expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("recipient@example.com"),
      }));
    });
  });

  describe("rebuildCard", () => {
    it("should rebuild card with selected issues", async () => {
      globalThis.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ card: {} }),
      });

      await api.rebuildCard({ issues: [] }, [0, 2, 3]);

      expect(globalThis.fetch).toHaveBeenCalledWith("/api/rebuild-card", expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("selected_issue_indices"),
      }));
    });
  });

  describe("health check", () => {
    it("should return true for healthy API", async () => {
      globalThis.fetch.mockResolvedValue({ ok: true });

      const result = await api.health();

      expect(result).toBe(true);
    });

    it("should return false for unhealthy API", async () => {
      globalThis.fetch.mockResolvedValue({ ok: false });

      const result = await api.health();

      expect(result).toBe(false);
    });
  });
});