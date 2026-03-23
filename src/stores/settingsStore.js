import { create } from "zustand";
import { persist } from "zustand/middleware";

// Claude Haiku 4.5  — used for audit
const HAIKU_INPUT_COST = 0.8;
const HAIKU_OUTPUT_COST = 4;
// Claude Sonnet 4.6 — used for email
const SONNET_INPUT_COST = 3;
const SONNET_OUTPUT_COST = 15;

export const useSettingsStore = create(
  persist(
    (set) => ({
      // AI
      aiProvider: "ollama",
      ollamaBaseUrl: "http://localhost:11434",
      ollamaModel: "qwen3.5:9b",
      openaiApiKey: "",
      openaiModel: "gpt-4o-mini",
      anthropicApiKey: "",
      anthropicModel: "claude-sonnet-4-6",

      // Screenshot service
      screenshotServiceUrl: "http://localhost:3000",

      // Scan
      maxDeepPages: 20,

      // Email / identity
      yourName: "Marcin Zielinski",
      yourTitle: "English Localization Specialist & Full-Stack Developer",
      yourEmail: "",
      yourWebsite: "https://imrie83.github.io/shinrai/",

      // Gmail SMTP
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
      // Saved searches: [{ id, keywords, location, label? }]
      savedSearches: [],
      // Previously used keywords for autocomplete suggestions
      usedKeywords: [],

      // Dual model: separate model for email writing
      emailAiProvider: "ollama", // provider for email generation
      emailAnthropicModel: "claude-haiku-4-5-20251001", // haiku for audit, sonnet for email by default
      emailOllamaModel: "qwen3.5:9b",
      emailOpenaiModel: "gpt-4o",

      // Token cost — audit (Haiku by default)
      auditInputCostPer1M: HAIKU_INPUT_COST,
      auditOutputCostPer1M: HAIKU_OUTPUT_COST,
      // Token cost — email (Sonnet by default)
      emailInputCostPer1M: SONNET_INPUT_COST,
      emailOutputCostPer1M: SONNET_OUTPUT_COST,

      setField: (key, value) => set({ [key]: value }),
      setMany: (obj) => set(obj),
    }),
    { name: "prism-settings" }
  )
);
