import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useAISettings } from "./useAISettings.js";
import { useSettingsStore } from "../stores/settingsStore.js";

// Mock Zustand store
vi.mock("../stores/settingsStore.js", () => ({
  useSettingsStore: vi.fn(),
}));

describe("useAISettings", () => {
  const mockSettings = {
    aiProvider: "ollama",
    ollamaBaseUrl: "http://localhost:11434",
    ollamaModel: "qwen3.5:9b",
    openaiApiKey: "sk-test",
    openaiModel: "gpt-4o-mini",
    anthropicApiKey: "sk-ant-test",
    anthropicModel: "claude-sonnet-4-6",
    screenshotServiceUrl: "http://localhost:3000",
    emailAiProvider: "claude",
    emailOllamaModel: "llama3",
    emailOpenaiModel: "gpt-4o",
    emailAnthropicModel: "claude-sonnet-4-6",
    yourName: "Test User",
    yourTitle: "Developer",
    yourEmail: "test@example.com",
    yourWebsite: "https://test.com",
  };

  beforeEach(() => {
    vi.clearAllMocks();
    useSettingsStore.mockReturnValue(mockSettings);
  });

  describe("getScanSettings", () => {
    it("should return scan settings from the store", () => {
      const { result } = renderHook(() => useAISettings());
      const settings = result.current.getScanSettings();

      expect(settings).toEqual({
        ai_provider: "ollama",
        ollama_base_url: "http://localhost:11434",
        ollama_model: "qwen3.5:9b",
        openai_api_key: "sk-test",
        openai_model: "gpt-4o-mini",
        anthropic_api_key: "sk-ant-test",
        anthropic_model: "claude-sonnet-4-6",
        screenshot_service_url: "http://localhost:3000",
      });
    });

    it("should use different provider when changed", () => {
      useSettingsStore.mockReturnValue({
        ...mockSettings,
        aiProvider: "openai",
      });

      const { result } = renderHook(() => useAISettings());
      const settings = result.current.getScanSettings();

      expect(settings.ai_provider).toBe("openai");
    });
  });

  describe("getEmailSettings", () => {
    it("should return email settings with fallback to scan provider", () => {
      useSettingsStore.mockReturnValue({
        ...mockSettings,
        aiProvider: "ollama",
        emailAiProvider: null, // Falls back to aiProvider
      });

      const { result } = renderHook(() => useAISettings());
      const settings = result.current.getEmailSettings();

      expect(settings.ai_provider).toBe("ollama");
    });

    it("should use email-specific provider when set", () => {
      const { result } = renderHook(() => useAISettings());
      const settings = result.current.getEmailSettings();

      expect(settings.ai_provider).toBe("claude");
    });

    it("should use email-specific models for each provider", () => {
      const { result } = renderHook(() => useAISettings());
      const settings = result.current.getEmailSettings();

      // Uses email-specific Anthropic model since emailAiProvider is "claude"
      expect(settings.anthropic_model).toBe("claude-sonnet-4-6");
    });

    it("should include identity fields in email settings", () => {
      const { result } = renderHook(() => useAISettings());
      const settings = result.current.getEmailSettings();

      expect(settings.your_name).toBe("Test User");
      expect(settings.your_title).toBe("Developer");
      expect(settings.your_email).toBe("test@example.com");
      expect(settings.your_website).toBe("https://test.com");
    });

    it("should fallback to main model when email-specific model not set", () => {
      useSettingsStore.mockReturnValue({
        ...mockSettings,
        emailAiProvider: "ollama",
        emailOllamaModel: null, // Should fallback to ollamaModel
        ollamaModel: "qwen3.5:9b",
      });

      const { result } = renderHook(() => useAISettings());
      const settings = result.current.getEmailSettings();

      expect(settings.ollama_model).toBe("qwen3.5:9b");
    });
  });
});