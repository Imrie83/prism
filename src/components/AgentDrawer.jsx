import { useRef, useEffect, useState } from "react";
import { X, Send, Bot } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useAgentStore } from "../stores/agentStore";
import { useScanStore } from "../stores/scanStore";
import { useAISettings } from "../hooks/useAISettings";
import { api } from "../lib/api";

export default function AgentDrawer() {
  const { isOpen, messages, status, setOpen, addMessage, setStatus } = useAgentStore();
  const { getScanSettings } = useAISettings();
  const { deepHistory, shallowHistory, deepActiveRun, shallowActiveRun } = useScanStore();
  const [input, setInput] = useState("");
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Build compact scan context for the agent
  const scanContext = (() => {
    // Use latest deep scan if available, otherwise latest shallow
    const deepRun = deepHistory.find(r => r.runId === deepActiveRun) || deepHistory[0];
    if (deepRun?.pages?.length > 0) {
      return deepRun.pages.map(p =>
        `Page: ${p.url}\nTitle: ${p.title || "Unknown"}\nScore: ${p.result?.score ?? "N/A"}\nIssues: ${
          (p.result?.issues || []).map(i => `[${i.severity}] ${i.type}: ${i.explanation}`).join("; ")
        }`
      ).join("\n\n");
    }
    const shallowRun = shallowHistory.find(r => r.runId === shallowActiveRun) || shallowHistory[0];
    if (shallowRun?.result) {
      const result = shallowRun.result;
      return `Page: ${result.url || "scanned page"}\nScore: ${result.score}\nIssues: ${
        (result.issues || []).map(i => `[${i.severity}] ${i.type}: ${i.explanation}`).join("; ")
      }`;
    }
    return "No scan data available yet.";
  })();

  async function send() {
    const text = input.trim();
    if (!text || status === "thinking") return;
    setInput("");
    addMessage({ role: "user", content: text });
    setStatus("thinking");
    try {
      const history = [...messages, { role: "user", content: text }];
      const data = await api.agentChat(history, scanContext, getScanSettings());
      addMessage({ role: "assistant", content: data.reply });
    } catch (e) {
      addMessage({ role: "assistant", content: `Error: ${e.message}` });
    } finally {
      setStatus("idle");
    }
  }

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  }

  return (
    <>
      {/* Backdrop for mobile */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={() => setOpen(false)}
            style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 49,
              display: "none" }}
            className="agent-backdrop"
          />
        )}
      </AnimatePresence>

      <div className={`agent-drawer${isOpen ? " agent-drawer--open" : ""}`}>
        <div className="agent-drawer__header">
          <div className="flex items-center gap-8">
            <Bot size={16} color="var(--blue)" />
            <h3>Audit Agent</h3>
            {status === "thinking" && <div className="spinner" />}
          </div>
          <button className="btn btn--ghost btn--icon btn--sm" onClick={() => setOpen(false)}>
            <X size={15} />
          </button>
        </div>

        <div className="agent-drawer__messages">
          {messages.length === 0 && (
            <div style={{ color: "var(--ink3)", fontSize: 12, fontStyle: "italic", padding: "8px 0" }}>
              Ask me anything about the scan results — specific issues, recommendations, how to fix something...
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={`agent-drawer__msg agent-drawer__msg--${msg.role}`}>
              {msg.content}
            </div>
          ))}
          {status === "thinking" && (
            <div className="agent-drawer__msg agent-drawer__msg--thinking">Thinking…</div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="agent-drawer__input">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask about the results… (Enter to send)"
            rows={2}
          />
          <button className="btn btn--primary btn--icon" onClick={send} disabled={!input.trim() || status === "thinking"}>
            <Send size={14} />
          </button>
        </div>
      </div>
    </>
  );
}
