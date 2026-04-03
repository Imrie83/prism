import { motion, AnimatePresence } from "framer-motion";
import { Scan, BarChart3, Settings, Bot, Sun, Moon, History, Compass } from "lucide-react";
import { useScanStore } from "../stores/scanStore";
import { useAgentStore } from "../stores/agentStore";
import { useEmailStore } from "../stores/emailStore";

const DOT_COLOR = {
  queued:     "#6b7280",
  generating: "var(--blue)",
  ready:      "#22c55e",
  error:      "var(--red)",
  sent:       "#22c55e",
  scheduled:  "#a78bfa",
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
      style={{ overflow: "hidden", display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}
    >
      <div style={{ padding: "8px 12px 4px", flexShrink: 0 }}>
        <span style={{
          fontSize: 10, fontWeight: 600, letterSpacing: "0.1em",
          textTransform: "uppercase", color: "var(--ink3)", fontFamily: "var(--font-mono)"
        }}>
          Email Queue
        </span>
      </div>
      <style>{`.eq-scroll::-webkit-scrollbar{display:none}`}</style>
      <div className="eq-scroll" style={{ overflowY: "auto", scrollbarWidth: "none", flex: 1, minHeight: 0 }}>
        {entries.map(([url, data]) => {
          let hostname = url;
          try { hostname = new URL(url).hostname; } catch {}
          const dotColor = DOT_COLOR[data.status] || "#6b7280";
          return (
            <button key={url}
              onClick={() => handleClick(url)}
              className="sidebar__item"
              style={{
                display: "flex", alignItems: "center", gap: 8,
                width: "100%", cursor: "pointer",
              }}
            >
              <motion.div
                animate={data.status === "generating"
                  ? { scale: [1, 1.5, 1], opacity: [1, 0.4, 1] } : {}}
                transition={{ repeat: Infinity, duration: 0.9, ease: "easeInOut" }}
                style={{
                  width: 7, height: 7, borderRadius: "50%", flexShrink: 0,
                  background: dotColor,
                  boxShadow: data.status === "generating" ? "0 0 8px var(--blue)" : "none",
                }}
              />
              <span style={{
                fontSize: 11, color: "var(--ink2)", fontFamily: "var(--font-mono)",
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1,
              }}>
                {hostname}
              </span>
              <span style={{ fontSize: 10, color: dotColor, flexShrink: 0, fontFamily: "var(--font-mono)" }}>
                {data.status}
              </span>
            </button>
          );
        })}
      </div>
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

        <button
          className={`sidebar__item${activeTab === "history" ? " sidebar__item--active" : ""}`}
          onClick={() => setActiveTab("history")}>
          <History size={15} /> History
        </button>

        <button
          className={`sidebar__item${activeTab === "discover" ? " sidebar__item--active" : ""}`}
          onClick={() => setActiveTab("discover")}>
          <Compass size={15} /> Discover
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
