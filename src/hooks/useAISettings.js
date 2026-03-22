/**
 * useAISettings — shared hook that builds the AI settings objects
 * needed for scan and email API calls from the settings store.
 *
 * Eliminates duplicate getAISettings() / getEmailAISettings() functions
 * that previously existed in ScanPage and DiscoverPage.
 */
import { useSettingsStore } from "../stores/settingsStore";

export function useAISettings() {
  const s = useSettingsStore();

  /** Settings for the audit/scan AI call */
  function getScanSettings() {
    return {
      ai_provider:            s.aiProvider,
      ollama_base_url:        s.ollamaBaseUrl,
      ollama_model:           s.ollamaModel,
      openai_api_key:         s.openaiApiKey,
      openai_model:           s.openaiModel,
      anthropic_api_key:      s.anthropicApiKey,
      anthropic_model:        s.anthropicModel,
      screenshot_service_url: s.screenshotServiceUrl,
    };
  }

  /** Settings for the email generation AI call (may use a different model) */
  function getEmailSettings() {
    const provider = s.emailAiProvider || s.aiProvider;
    return {
      ai_provider:       provider,
      ollama_base_url:   s.ollamaBaseUrl,
      ollama_model:      provider === "ollama" ? (s.emailOllamaModel    || s.ollamaModel)    : s.ollamaModel,
      openai_api_key:    s.openaiApiKey,
      openai_model:      provider === "openai" ? (s.emailOpenaiModel    || s.openaiModel)    : s.openaiModel,
      anthropic_api_key: s.anthropicApiKey,
      anthropic_model:   provider === "claude" ? (s.emailAnthropicModel || s.anthropicModel) : s.anthropicModel,
      your_name:         s.yourName,
      your_title:        s.yourTitle,
      your_email:        s.yourEmail,
      your_website:      s.yourWebsite,
    };
  }

  return { getScanSettings, getEmailSettings };
}
