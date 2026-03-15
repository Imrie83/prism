import { X, Eye, EyeOff, CheckCircle, XCircle, Loader } from "lucide-react";
import { useState } from "react";
import { useSettingsStore } from "../stores/settingsStore";

function PasswordField({ label, fieldKey }) {
  const [show, setShow] = useState(false);
  const value = useSettingsStore(s => s[fieldKey]);
  const setField = useSettingsStore(s => s.setField);

  return (
    <div className="field">
      <label>{label}</label>
      <div style={{ position: "relative" }}>
        <input
          type={show ? "text" : "password"}
          value={value}
          onChange={e => setField(fieldKey, e.target.value)}
          style={{ paddingRight: 40 }}
        />
        <button
          onClick={() => setShow(s => !s)}
          style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
            color: "var(--ink3)", padding: 4 }}
        >
          {show ? <EyeOff size={14} /> : <Eye size={14} />}
        </button>
      </div>
    </div>
  );
}

export default function SettingsModal({ onClose }) {
  const s = useSettingsStore();
  const [testResult, setTestResult] = useState(null); // null | "testing" | {success, ...}

  async function testConnection() {
    setTestResult("testing");
    try {
      const res = await fetch("/api/test-ai", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: "test",
          settings: {
            ai_provider: s.aiProvider,
            ollama_base_url: s.ollamaBaseUrl,
            ollama_model: s.ollamaModel,
            openai_api_key: s.openaiApiKey,
            openai_model: s.openaiModel,
            anthropic_api_key: s.anthropicApiKey,
            anthropic_model: s.anthropicModel,
            screenshot_service_url: s.screenshotServiceUrl,
            max_deep_pages: s.maxDeepPages,
          },
        }),
      });
      const data = await res.json();
      setTestResult(data);
    } catch (e) {
      setTestResult({ success: false, error: e.message });
    }
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal__header">
          <h2>Settings</h2>
          <button className="btn btn--ghost btn--icon btn--sm" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="modal__body">

          {/* AI Provider */}
          <div className="modal__section">
            <h3>AI Provider</h3>
            <div className="field">
              <label>Provider</label>
              <select value={s.aiProvider} onChange={e => s.setField("aiProvider", e.target.value)}>
                <option value="ollama">Ollama (local)</option>
                <option value="openai">OpenAI</option>
                <option value="claude">Anthropic Claude</option>
              </select>
            </div>

            {s.aiProvider === "ollama" && (
              <div className="field-row">
                <div className="field">
                  <label>Ollama Base URL</label>
                  <input value={s.ollamaBaseUrl} onChange={e => s.setField("ollamaBaseUrl", e.target.value)} />
                </div>
                <div className="field">
                  <label>Model</label>
                  <input value={s.ollamaModel} onChange={e => s.setField("ollamaModel", e.target.value)}
                    placeholder="qwen3.5:9b" />
                </div>
              </div>
            )}

            {s.aiProvider === "openai" && (
              <div className="field-row">
                <PasswordField label="OpenAI API Key" fieldKey="openaiApiKey" />
                <div className="field">
                  <label>Model</label>
                  <input value={s.openaiModel} onChange={e => s.setField("openaiModel", e.target.value)}
                    placeholder="gpt-4o-mini" />
                </div>
              </div>
            )}

            {s.aiProvider === "claude" && (
              <div className="field-row">
                <PasswordField label="Anthropic API Key" fieldKey="anthropicApiKey" />
                <div className="field">
                  <label>Model</label>
                  <input value={s.anthropicModel} onChange={e => s.setField("anthropicModel", e.target.value)}
                    placeholder="claude-sonnet-4-6" />
                </div>
              </div>
            )}
          </div>

          {/* Services */}
          <div className="modal__section">
            <h3>Services</h3>
            <div className="field-row">
              <div className="field">
                <label>Screenshot Service URL</label>
                <input value={s.screenshotServiceUrl}
                  onChange={e => s.setField("screenshotServiceUrl", e.target.value)} />
              </div>
              <div className="field">
                <label>Max Deep Scan Pages</label>
                <input type="number" min={1} max={50} value={s.maxDeepPages}
                  onChange={e => s.setField("maxDeepPages", Number(e.target.value))} />
              </div>
            </div>
          </div>

          {/* Identity */}
          <div className="modal__section">
            <h3>Your Identity (for emails)</h3>
            <div className="field-row">
              <div className="field">
                <label>Your Name</label>
                <input value={s.yourName} onChange={e => s.setField("yourName", e.target.value)} />
              </div>
              <div className="field">
                <label>Your Title</label>
                <input value={s.yourTitle} onChange={e => s.setField("yourTitle", e.target.value)} />
              </div>
            </div>
            <div className="field-row">
              <div className="field">
                <label>Your Email</label>
                <input type="email" value={s.yourEmail}
                  onChange={e => s.setField("yourEmail", e.target.value)} />
              </div>
              <div className="field">
                <label>Your Website</label>
                <input value={s.yourWebsite} onChange={e => s.setField("yourWebsite", e.target.value)} />
              </div>
            </div>
          </div>

          {/* Email AI Model */}
          <div className="modal__section">
            <h3>Email Generation Model</h3>
            <p className="text-muted text-sm mb-12">
              Use a smarter/different model just for writing emails. Leave same as audit model if not needed.
            </p>
            <div className="field">
              <label>Email Provider</label>
              <select value={s.emailAiProvider} onChange={e => s.setField("emailAiProvider", e.target.value)}>
                <option value="ollama">Ollama (local)</option>
                <option value="openai">OpenAI</option>
                <option value="claude">Anthropic Claude</option>
              </select>
            </div>
            {s.emailAiProvider === "ollama" && (
              <div className="field">
                <label>Email Ollama Model</label>
                <input value={s.emailOllamaModel} onChange={e => s.setField("emailOllamaModel", e.target.value)} placeholder="qwen3.5:9b" />
              </div>
            )}
            {s.emailAiProvider === "openai" && (
              <div className="field">
                <label>Email OpenAI Model</label>
                <input value={s.emailOpenaiModel} onChange={e => s.setField("emailOpenaiModel", e.target.value)} placeholder="gpt-4o" />
              </div>
            )}
            {s.emailAiProvider === "claude" && (
              <div className="field">
                <label>Email Anthropic Model</label>
                <input value={s.emailAnthropicModel} onChange={e => s.setField("emailAnthropicModel", e.target.value)} placeholder="claude-sonnet-4-6" />
              </div>
            )}
          </div>

          {/* Token costs */}
          <div className="modal__section">
            <h3>Token Cost ($ per 1M tokens)</h3>
            <p className="text-muted text-sm mb-12">
              Shown in the token badge after each scan/email. Set both to 0 for local Ollama.
            </p>

            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--ink3)", textTransform: "uppercase",
              letterSpacing: "0.08em", marginBottom: 8 }}>
              Audit model (Haiku — $0.80 / $4.00 default)
            </div>
            <div className="field-row" style={{ marginBottom: 16 }}>
              <div className="field">
                <label>Input / 1M ($)</label>
                <input type="number" min={0} step={0.01} value={s.auditInputCostPer1M}
                  onChange={e => s.setField("auditInputCostPer1M", parseFloat(e.target.value) || 0)} />
              </div>
              <div className="field">
                <label>Output / 1M ($)</label>
                <input type="number" min={0} step={0.01} value={s.auditOutputCostPer1M}
                  onChange={e => s.setField("auditOutputCostPer1M", parseFloat(e.target.value) || 0)} />
              </div>
            </div>

            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--ink3)", textTransform: "uppercase",
              letterSpacing: "0.08em", marginBottom: 8 }}>
              Email model (Sonnet — $3.00 / $15.00 default)
            </div>
            <div className="field-row">
              <div className="field">
                <label>Input / 1M ($)</label>
                <input type="number" min={0} step={0.01} value={s.emailInputCostPer1M}
                  onChange={e => s.setField("emailInputCostPer1M", parseFloat(e.target.value) || 0)} />
              </div>
              <div className="field">
                <label>Output / 1M ($)</label>
                <input type="number" min={0} step={0.01} value={s.emailOutputCostPer1M}
                  onChange={e => s.setField("emailOutputCostPer1M", parseFloat(e.target.value) || 0)} />
              </div>
            </div>
          </div>

          {/* Gmail */}
          <div className="modal__section">
            <h3>Gmail SMTP</h3>
            <p className="text-muted text-sm mb-12">
              Requires a Gmail App Password — not your regular password.{" "}
              <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noopener noreferrer">
                Generate one here ↗
              </a>
            </p>
            <div className="field-row">
              <div className="field">
                <label>Gmail Address</label>
                <input type="email" value={s.gmailAddress}
                  onChange={e => s.setField("gmailAddress", e.target.value)} />
              </div>
              <PasswordField label="App Password" fieldKey="gmailAppPassword" />
            </div>
            <div className="field-row">
              <div className="field">
                <label>From Address (visible to recipient)</label>
                <input type="email" value={s.fromAddress}
                  placeholder="zielinski.marcin@shinrai.pro"
                  onChange={e => s.setField("fromAddress", e.target.value)} />
              </div>
            </div>
          </div>

        </div>

        <div className="modal__footer" style={{ flexDirection: "column", alignItems: "stretch", gap: 12 }}>
          {testResult && testResult !== "testing" && (
            <div style={{
              padding: "10px 14px", borderRadius: "var(--radius)",
              background: testResult.success ? "rgba(52,211,153,0.08)" : "rgba(248,113,113,0.08)",
              border: `1px solid ${testResult.success ? "rgba(52,211,153,0.3)" : "rgba(248,113,113,0.3)"}`,
              fontSize: 12, fontFamily: "var(--font-mono)",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                {testResult.success
                  ? <CheckCircle size={14} style={{ color: "var(--green)" }} />
                  : <XCircle    size={14} style={{ color: "var(--red)"   }} />}
                <strong style={{ color: testResult.success ? "var(--green)" : "var(--red)" }}>
                  {testResult.success ? "Connection OK" : "Connection failed"}
                </strong>
                {testResult.elapsed_s && (
                  <span style={{ color: "var(--ink3)", marginLeft: "auto" }}>{testResult.elapsed_s}s</span>
                )}
              </div>
              {testResult.success && (
                <>
                  <div style={{ color: "var(--ink2)" }}>
                    Model: {testResult.model} · {testResult.tokens?.total_tokens} tokens
                  </div>
                  <div style={{ color: testResult.json_parse_ok ? "var(--green)" : "var(--red)", marginTop: 4 }}>
                    JSON parse: {testResult.json_parse_ok ? "✓ OK" : `✗ ${testResult.json_parse_error}`}
                  </div>
                  <div style={{ color: "var(--ink3)", marginTop: 4, wordBreak: "break-all" }}>
                    Raw: {testResult.first_chars}
                  </div>
                </>
              )}
              {!testResult.success && (
                <div style={{ color: "var(--red)", marginTop: 4, wordBreak: "break-all" }}>
                  {testResult.error}
                </div>
              )}
            </div>
          )}
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <button className="btn btn--ghost" onClick={testConnection} disabled={testResult === "testing"}
              style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {testResult === "testing"
                ? <><Loader size={13} style={{ animation: "spin 1s linear infinite" }} /> Testing…</>
                : "Test AI Connection"}
            </button>
            <button className="btn btn--primary" onClick={onClose}>Done</button>
          </div>
        </div>
      </div>
    </div>
  );
}
