import { motion, AnimatePresence } from "framer-motion";
import { Scan, BarChart3, Settings, Bot, Sun, Moon } from "lucide-react";
import { useScanStore } from "../stores/scanStore";
import { useAgentStore } from "../stores/agentStore";
import { useEmailStore } from "../stores/emailStore";

const DOT_COLOR = {
  queued:     "var(--ink3)",
  generating: "var(--blue)",
  ready:      "var(--green)",
  error:      "var(--red)",
  sent:       "var(--accent)",
};

function EmailQueueStatus() {
  const emails = useEmailStore(s => s.emails);
  const openDrawerFor = useEmailStore(s => s.openDrawerFor);
  const setActiveTab = useScanStore(s => s.setActiveTab);
  const entries = Object.entries(emails);
  if (!entries.length) return null;

  function handleClick(url) {
    // Navigate to results then open the drawer for this URL
    setActiveTab("results");
    setTimeout(() => openDrawerFor(url), 80);
  }

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      style={{ overflow: "hidden" }}
    >
      <div style={{ padding: "8px 12px 4px" }}>
        <span style={{
          fontSize: 10, fontWeight: 600, letterSpacing: "0.1em",
          textTransform: "uppercase", color: "var(--ink3)", fontFamily: "var(--font-mono)"
        }}>
          Email Queue
        </span>
      </div>
      {entries.map(([url, data]) => {
        let hostname = url;
        try { hostname = new URL(url).hostname; } catch {}
        return (
          <motion.button key={url}
            initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            onClick={() => handleClick(url)}
            style={{
              display: "flex", alignItems: "center", gap: 8, padding: "5px 12px",
              width: "100%", background: "none", border: "none", cursor: "pointer",
              borderRadius: "var(--radius)", transition: "background 0.12s",
            }}
            whileHover={{ background: "var(--surface2)" }}
          >
            <motion.div
              animate={data.status === "generating"
                ? { scale: [1, 1.5, 1], opacity: [1, 0.4, 1] } : {}}
              transition={{ repeat: Infinity, duration: 0.9, ease: "easeInOut" }}
              style={{
                width: 7, height: 7, borderRadius: "50%", flexShrink: 0,
                background: DOT_COLOR[data.status] || "var(--ink3)",
                boxShadow: data.status === "generating" ? "0 0 8px var(--blue)" : "none",
              }}
            />
            <span style={{
              fontSize: 11, color: "var(--ink2)", fontFamily: "var(--font-mono)",
              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1,
            }}>
              {hostname}
            </span>
            <span style={{ fontSize: 10, color: DOT_COLOR[data.status], flexShrink: 0, fontFamily: "var(--font-mono)" }}>
              {data.status}
            </span>
          </motion.button>
        );
      })}
    </motion.div>
  );
}

export default function Sidebar({ onSettings, mobileOpen, darkMode, onToggleDark }) {
  const { activeTab, setActiveTab, hasAnyResults } = useScanStore();
  const { shallowHistory, deepHistory, batchHistory } = useScanStore();
  const { toggleOpen } = useAgentStore();

  const anyResults = hasAnyResults();
  const totalRuns = shallowHistory.length + deepHistory.length + batchHistory.length;

  function nav(tab) {
    if (tab === "results" && !anyResults) return;
    setActiveTab(tab);
  }

  return (
    <nav className={`sidebar${mobileOpen ? " sidebar--open" : ""}`}>
      <div className="sidebar__logo">
        <div className="logo-mark">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" style={{ flexShrink: 0 }}>
            <polygon points="9,1 17,16 1,16" stroke="url(#sg)" strokeWidth="1.5" fill="none" strokeLinejoin="round"/>
            <line x1="9" y1="1" x2="9" y2="16" stroke="#4db8ff" strokeWidth="0.8" opacity="0.5"/>
            <defs>
              <linearGradient id="sg" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#4db8ff"/>
                <stop offset="100%" stopColor="#a78bfa"/>
              </linearGradient>
            </defs>
          </svg>
          Prism
        </div>
        <div className="logo-sub">Site Audit Tool</div>
      </div>

      <div className="sidebar__nav">
        <span className="sidebar__section">Workspace</span>

        <button
          className={`sidebar__item${activeTab === "scan" ? " sidebar__item--active" : ""}`}
          onClick={() => nav("scan")}>
          <Scan size={15} /> Scan
        </button>

        <button
          className={`sidebar__item${activeTab === "results" ? " sidebar__item--active" : ""}${!anyResults ? " sidebar__item--disabled" : ""}`}
          onClick={() => nav("results")}>
          <BarChart3 size={15} /> Results
          {anyResults && (
            <motion.span className="sidebar__badge"
              initial={{ scale: 0 }} animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 400, damping: 18 }}>
              {totalRuns}
            </motion.span>
          )}
        </button>

        <span className="sidebar__section">Tools</span>

        <button className="sidebar__item" onClick={toggleOpen}>
          <Bot size={15} /> Audit Agent
        </button>

        <AnimatePresence>
          <EmailQueueStatus />
        </AnimatePresence>
      </div>

      <div className="sidebar__footer">
        <button className="sidebar__item" onClick={onToggleDark}>
          {darkMode ? <Sun size={15} /> : <Moon size={15} />}
          {darkMode ? "Light mode" : "Dark mode"}
        </button>
        <button className="sidebar__item" onClick={onSettings}>
          <Settings size={15} /> Settings
        </button>
      </div>
    </nav>
  );
}
