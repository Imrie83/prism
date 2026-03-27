import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { Menu, X } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import Sidebar from "./components/Sidebar";
import AgentDrawer from "./components/AgentDrawer";
import EmailDrawer from "./components/EmailDrawer";
import SettingsModal from "./components/SettingsModal";
import ScanPage from "./pages/ScanPage";
import ResultsPage from "./pages/ResultsPage";
import HistoryPage from "./pages/HistoryPage";
import DiscoverPage from "./pages/DiscoverPage";
import { useScanStore } from "./stores/scanStore";
import { useEmailStore } from "./stores/emailStore";
import { useAgentStore } from "./stores/agentStore";
import { useEmailStatusPoller } from "./hooks/useEmailStatusPoller";

const VERSION = __APP_VERSION__;

const TAB_TITLES = {
  scan: "New Audit",
  results: "Results",
  history: "Outreach History",
  discover: "Discover",
};

// Read computed CSS clamp value for --email-w
function getEmailDrawerWidth() {
  if (typeof window === "undefined") return 640;
  const w = getComputedStyle(document.documentElement)
    .getPropertyValue("--email-w").trim();
  // clamp returns a string like "clamp(580px, 38vw, 800px)" — evaluate it
  const test = document.createElement("div");
  test.style.width = w || "640px";
  test.style.position = "absolute";
  test.style.visibility = "hidden";
  document.body.appendChild(test);
  const px = test.offsetWidth;
  document.body.removeChild(test);
  return px || 640;
}

export default function App() {
  const { activeTab } = useScanStore();
  const { drawerUrl } = useEmailStore();
  const { isOpen: agentOpen } = useAgentStore();
  const [showSettings, setShowSettings] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(true);
  const emailW = useRef(640);

  // ── Global email status poller ────────────────────────────────────────────
  // Collects all URLs from the scan store (shallow/deep/batch results) and polls
  // for email status changes. applyEmailStatusToStore (called inside the hook)
  // updates the emailStore so EmailDrawer + ResultsPage reflect live state.
  // The History and Discover pages add their own onUpdate callbacks on top of this.
  const store = useScanStore();
  const globalPollUrls = useMemo(() => {
    const urls = new Set();
    store.shallowHistory.forEach(r => r.result?.url && urls.add(r.result.url));
    store.deepHistory.forEach(r => r.pages?.forEach(p => p.result?.url && urls.add(p.result.url)));
    store.batchHistory.forEach(r => r.results?.forEach(p => p.result?.url && urls.add(p.result.url)));
    return [...urls];
  }, [store.shallowHistory, store.deepHistory, store.batchHistory]);
  // No onUpdate needed here — applyEmailStatusToStore inside the hook does the work
  useEmailStatusPoller(globalPollUrls, null, 6000);

  useEffect(() => {
    const saved = localStorage.getItem("prism-theme");
    if (saved === "light") { setDarkMode(false); document.body.classList.add("light"); }
    emailW.current = getEmailDrawerWidth();
    window.addEventListener("resize", () => { emailW.current = getEmailDrawerWidth(); });
  }, []);

  function toggleDark() {
    setDarkMode(d => {
      const next = !d;
      if (next) { document.body.classList.remove("light"); localStorage.setItem("prism-theme", "dark"); }
      else { document.body.classList.add("light"); localStorage.setItem("prism-theme", "light"); }
      return next;
    });
  }

  const drawerMargin = drawerUrl ? emailW.current : agentOpen ? 360 : 0;

  return (
    <div className="app">
      <div className="bg-grid" />

      <Sidebar
        onSettings={() => setShowSettings(true)}
        mobileOpen={mobileSidebarOpen}
        darkMode={darkMode}
        onToggleDark={toggleDark}
      />

      {mobileSidebarOpen && (
        <div onClick={() => setMobileSidebarOpen(false)}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 39 }} />
      )}

      <motion.div
        className="main"
        animate={{ marginRight: drawerMargin }}
        transition={{ type: "spring", stiffness: 300, damping: 32 }}
        style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}
      >
        <div className="topbar" style={{ position: "relative" }}>
          <button id="mobile-menu-btn" className="btn btn--ghost btn--icon btn--sm"
            onClick={() => setMobileSidebarOpen(o => !o)}>
            {mobileSidebarOpen ? <X size={17} /> : <Menu size={17} />}
          </button>
          <span className="topbar__title">{TAB_TITLES[activeTab] ?? activeTab}</span>
          <div className="topbar__actions">
            <span style={{ fontSize: 11, color: "var(--ink3)", fontFamily: "var(--font-mono)" }}>
              v{VERSION}
            </span>
          </div>
        </div>

        <AnimatePresence mode="wait">
          <motion.div key={activeTab}
            initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }} transition={{ duration: 0.16 }}
            style={{ flex: 1 }}>
            {activeTab === "scan" && <ScanPage />}
            {activeTab === "results" && <ResultsPage />}
            {activeTab === "history" && <HistoryPage />}
            {activeTab === "discover" && <DiscoverPage />}
          </motion.div>
        </AnimatePresence>
      </motion.div>

      {/* Drawers — no backdrop, results stay fully interactive */}
      <AgentDrawer />
      <EmailDrawer />

      <AnimatePresence>
        {showSettings && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}>
            <SettingsModal onClose={() => setShowSettings(false)} />
          </motion.div>
        )}
      </AnimatePresence>

      <style>{`
        @media (max-width: 768px) { #mobile-menu-btn { display: flex !important; } }
      `}</style>
    </div>
  );
}
