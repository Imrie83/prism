import { describe, it, expect, beforeEach } from "vitest";
import { useDiscoverStore } from "./discoverStore.js";

describe("discoverStore", () => {
  beforeEach(() => {
    useDiscoverStore.setState({
      keywords: "",
      location: "",
      limit: 120,
      searching: false,
      searchError: null,
      searchStats: null,
      searchProgress: null,
      sessions: [],
      activeSession: null,
      records: [],
      loading: false,
      page: 1,
      selected: [],
      scanningUrl: null,
      showFilters: false,
      showSuggestions: false,
    });
  });

  describe("form state", () => {
    it("should set keywords", () => {
      useDiscoverStore.getState().setField("keywords", "restaurant");
      expect(useDiscoverStore.getState().keywords).toBe("restaurant");
    });

    it("should set location", () => {
      useDiscoverStore.getState().setField("location", "Tokyo");
      expect(useDiscoverStore.getState().location).toBe("Tokyo");
    });

    it("should set limit", () => {
      useDiscoverStore.getState().setField("limit", 50);
      expect(useDiscoverStore.getState().limit).toBe(50);
    });

    it("should set multiple fields at once", () => {
      useDiscoverStore.getState().set({ keywords: "hotel", location: "Osaka" });
      const state = useDiscoverStore.getState();
      expect(state.keywords).toBe("hotel");
      expect(state.location).toBe("Osaka");
    });
  });

  describe("selection", () => {
    it("should toggle selection for a website", () => {
      useDiscoverStore.getState().toggleSelect("https://example.com");
      expect(useDiscoverStore.getState().selected).toContain("https://example.com");

      useDiscoverStore.getState().toggleSelect("https://example.com");
      expect(useDiscoverStore.getState().selected).not.toContain("https://example.com");
    });

    it("should toggle select all", () => {
      const urls = ["https://a.com", "https://b.com", "https://c.com"];

      useDiscoverStore.getState().toggleSelectAll(urls);
      expect(useDiscoverStore.getState().selected).toEqual(urls);

      useDiscoverStore.getState().toggleSelectAll(urls);
      expect(useDiscoverStore.getState().selected).toEqual([]);
    });

    it("should clear selection", () => {
      useDiscoverStore.getState().toggleSelect("https://a.com");
      useDiscoverStore.getState().toggleSelect("https://b.com");

      useDiscoverStore.getState().clearSelected();
      expect(useDiscoverStore.getState().selected).toEqual([]);
    });

    it("should remove from selected", () => {
      useDiscoverStore.getState().toggleSelect("https://a.com");
      useDiscoverStore.getState().toggleSelect("https://b.com");

      useDiscoverStore.getState().removeFromSelected("https://a.com");
      expect(useDiscoverStore.getState().selected).toEqual(["https://b.com"]);
    });
  });

  describe("records", () => {
    it("should update a single record", () => {
      useDiscoverStore.setState({
        records: [
          { website: "https://a.com", name: "A", status: "new" },
          { website: "https://b.com", name: "B", status: "new" },
        ],
      });

      useDiscoverStore.getState().updateRecord("https://a.com", { status: "scanned" });

      const state = useDiscoverStore.getState();
      expect(state.records[0].status).toBe("scanned");
      expect(state.records[1].status).toBe("new");
    });

    it("should remove a record", () => {
      useDiscoverStore.setState({
        records: [
          { website: "https://a.com", name: "A" },
          { website: "https://b.com", name: "B" },
        ],
        selected: ["https://a.com", "https://b.com"],
      });

      useDiscoverStore.getState().removeRecord("https://a.com");

      const state = useDiscoverStore.getState();
      expect(state.records).toHaveLength(1);
      expect(state.records[0].website).toBe("https://b.com");
      expect(state.selected).not.toContain("https://a.com");
    });
  });

  describe("search state", () => {
    it("should track searching state", () => {
      useDiscoverStore.getState().setField("searching", true);
      expect(useDiscoverStore.getState().searching).toBe(true);
    });

    it("should track search error", () => {
      useDiscoverStore.getState().setField("searchError", "Connection timeout");
      expect(useDiscoverStore.getState().searchError).toBe("Connection timeout");
    });

    it("should track search progress", () => {
      useDiscoverStore.getState().setField("searchProgress", { type: "scroll", count: 50 });
      expect(useDiscoverStore.getState().searchProgress.type).toBe("scroll");
    });
  });

  describe("pagination", () => {
    it("should track current page", () => {
      useDiscoverStore.getState().setField("page", 3);
      expect(useDiscoverStore.getState().page).toBe(3);
    });
  });

  describe("UI toggles", () => {
    it("should toggle filters visibility", () => {
      useDiscoverStore.getState().setField("showFilters", true);
      expect(useDiscoverStore.getState().showFilters).toBe(true);
    });

    it("should toggle suggestions visibility", () => {
      useDiscoverStore.getState().setField("showSuggestions", true);
      expect(useDiscoverStore.getState().showSuggestions).toBe(true);
    });
  });

  describe("sessions", () => {
    it("should set active session", () => {
      useDiscoverStore.getState().setField("activeSession", "session-123");
      expect(useDiscoverStore.getState().activeSession).toBe("session-123");
    });

    it("should store sessions list", () => {
      const sessions = [{ id: "s1", name: "Session 1" }];
      useDiscoverStore.getState().setField("sessions", sessions);
      expect(useDiscoverStore.getState().sessions).toEqual(sessions);
    });
  });
});