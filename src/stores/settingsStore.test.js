import { describe, it, expect, beforeEach, vi } from "vitest";
import { useSettingsStore } from "./settingsStore.js";

// Clear localStorage before each test
beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe("settingsStore", () => {
  beforeEach(() => {
    // Reset to default values
    useSettingsStore.setState({
      aiProvider: "ollama",
      ollamaBaseUrl: "http://localhost:11434",
      ollamaModel: "qwen3.5:9b",
      openaiApiKey: "",
      openaiModel: "gpt-4o-mini",
      anthropicApiKey: "",
      anthropicModel: "claude-sonnet-4-6",
      screenshotServiceUrl: "http://localhost:3000",
      maxDeepPages: 20,
      yourName: "Marcin Zielinski",
      yourTitle: "English Localization Specialist & Full-Stack Developer",
      yourEmail: "",
      yourWebsite: "https://imrie83.github.io/shinrai/",
      gmailAddress: "",
      gmailAppPassword: "",
      fromAddress: "zielinski.marcin@shinrai.pro",
      autoGenerateEmail: false,
      historyPerPage: 15,
      visionMode: false,
      historySortBy: "scanned_at",
      historySortDir: "desc",
      historyFilterEmail: "all",
      historyFilterScoreMin: 0,
      historyFilterScoreMax: 100,
      discoverPerPage: 25,
      discoverSortBy: "discovered_at",
      discoverSortDir: "desc",
      discoverFilterStatus: "all",
      discoverFilterHasEmail: "all",
      savedSearches: [],
      usedKeywords: [],
      emailAiProvider: "ollama",
      emailAnthropicModel: "claude-haiku-4-5-20251001",
      emailOllamaModel: "qwen3.5:9b",
      emailOpenaiModel: "gpt-4o",
      auditInputCostPer1M: 0.8,
      auditOutputCostPer1M: 4,
      emailInputCostPer1M: 3,
      emailOutputCostPer1M: 15,
    });
  });

  describe("AI provider settings", () => {
    it("should have default AI provider as ollama", () => {
      expect(useSettingsStore.getState().aiProvider).toBe("ollama");
    });

    it("should set AI provider", () => {
      useSettingsStore.getState().setField("aiProvider", "openai");
      expect(useSettingsStore.getState().aiProvider).toBe("openai");
    });

    it("should set API keys", () => {
      useSettingsStore.getState().setField("openaiApiKey", "sk-test-123");
      useSettingsStore.getState().setField("anthropicApiKey", "sk-ant-test");

      const state = useSettingsStore.getState();
      expect(state.openaiApiKey).toBe("sk-test-123");
      expect(state.anthropicApiKey).toBe("sk-ant-test");
    });

    it("should set Ollama settings", () => {
      useSettingsStore.getState().setField("ollamaBaseUrl", "http://192.168.1.1:11434");
      useSettingsStore.getState().setField("ollamaModel", "llama3");

      const state = useSettingsStore.getState();
      expect(state.ollamaBaseUrl).toBe("http://192.168.1.1:11434");
      expect(state.ollamaModel).toBe("llama3");
    });
  });

  describe("identity settings", () => {
    it("should set user name and title", () => {
      useSettingsStore.getState().setField("yourName", "John Doe");
      useSettingsStore.getState().setField("yourTitle", "Software Engineer");

      const state = useSettingsStore.getState();
      expect(state.yourName).toBe("John Doe");
      expect(state.yourTitle).toBe("Software Engineer");
    });

    it("should set email and website", () => {
      useSettingsStore.getState().setField("yourEmail", "john@example.com");
      useSettingsStore.getState().setField("yourWebsite", "https://johndoe.com");

      const state = useSettingsStore.getState();
      expect(state.yourEmail).toBe("john@example.com");
      expect(state.yourWebsite).toBe("https://johndoe.com");
    });
  });

  describe("email AI settings", () => {
    it("should have separate email AI provider", () => {
      useSettingsStore.getState().setField("emailAiProvider", "claude");
      expect(useSettingsStore.getState().emailAiProvider).toBe("claude");
    });

    it("should have separate email models per provider", () => {
      useSettingsStore.getState().setField("emailAnthropicModel", "claude-sonnet-4-6");
      useSettingsStore.getState().setField("emailOpenaiModel", "gpt-4o");
      useSettingsStore.getState().setField("emailOllamaModel", "qwen3:8b");

      const state = useSettingsStore.getState();
      expect(state.emailAnthropicModel).toBe("claude-sonnet-4-6");
      expect(state.emailOpenaiModel).toBe("gpt-4o");
      expect(state.emailOllamaModel).toBe("qwen3:8b");
    });
  });

  describe("scan settings", () => {
    it("should set max deep pages", () => {
      useSettingsStore.getState().setField("maxDeepPages", 50);
      expect(useSettingsStore.getState().maxDeepPages).toBe(50);
    });

    it("should set vision mode", () => {
      useSettingsStore.getState().setField("visionMode", true);
      expect(useSettingsStore.getState().visionMode).toBe(true);
    });
  });

  describe("history settings", () => {
    it("should set history pagination and sorting", () => {
      useSettingsStore.getState().setField("historyPerPage", 25);
      useSettingsStore.getState().setField("historySortBy", "url");
      useSettingsStore.getState().setField("historySortDir", "asc");

      const state = useSettingsStore.getState();
      expect(state.historyPerPage).toBe(25);
      expect(state.historySortBy).toBe("url");
      expect(state.historySortDir).toBe("asc");
    });

    it("should set history filters", () => {
      useSettingsStore.getState().setField("historyFilterEmail", "sent");
      useSettingsStore.getState().setField("historyFilterScoreMin", 50);
      useSettingsStore.getState().setField("historyFilterScoreMax", 90);

      const state = useSettingsStore.getState();
      expect(state.historyFilterEmail).toBe("sent");
      expect(state.historyFilterScoreMin).toBe(50);
      expect(state.historyFilterScoreMax).toBe(90);
    });
  });

  describe("discover settings", () => {
    it("should set discover pagination and sorting", () => {
      useSettingsStore.getState().setField("discoverPerPage", 50);
      useSettingsStore.getState().setField("discoverSortBy", "name");
      useSettingsStore.getState().setField("discoverSortDir", "asc");

      const state = useSettingsStore.getState();
      expect(state.discoverPerPage).toBe(50);
      expect(state.discoverSortBy).toBe("name");
      expect(state.discoverSortDir).toBe("asc");
    });

    it("should set discover filters", () => {
      useSettingsStore.getState().setField("discoverFilterStatus", "scanned");
      useSettingsStore.getState().setField("discoverFilterHasEmail", "yes");

      const state = useSettingsStore.getState();
      expect(state.discoverFilterStatus).toBe("scanned");
      expect(state.discoverFilterHasEmail).toBe("yes");
    });
  });

  describe("saved searches", () => {
    it("should add saved searches", () => {
      const search1 = { id: "s1", keywords: "hotel", location: "Tokyo" };
      useSettingsStore.getState().setField("savedSearches", [search1]);

      expect(useSettingsStore.getState().savedSearches).toHaveLength(1);
      expect(useSettingsStore.getState().savedSearches[0].keywords).toBe("hotel");
    });

    it("should track used keywords", () => {
      useSettingsStore.getState().setField("usedKeywords", ["restaurant", "hotel", "cafe"]);
      expect(useSettingsStore.getState().usedKeywords).toHaveLength(3);
    });
  });

  describe("token costs", () => {
    it("should have default token costs", () => {
      const state = useSettingsStore.getState();
      expect(state.auditInputCostPer1M).toBe(0.8);
      expect(state.auditOutputCostPer1M).toBe(4);
      expect(state.emailInputCostPer1M).toBe(3);
      expect(state.emailOutputCostPer1M).toBe(15);
    });

    it("should allow updating token costs", () => {
      useSettingsStore.getState().setField("auditInputCostPer1M", 1.5);
      expect(useSettingsStore.getState().auditInputCostPer1M).toBe(1.5);
    });
  });

  describe("setMany", () => {
    it("should set multiple fields at once", () => {
      useSettingsStore.getState().setMany({
        yourName: "Test User",
        yourEmail: "test@example.com",
        yourWebsite: "https://test.com",
      });

      const state = useSettingsStore.getState();
      expect(state.yourName).toBe("Test User");
      expect(state.yourEmail).toBe("test@example.com");
      expect(state.yourWebsite).toBe("https://test.com");
    });
  });
});