import { useEffect, useRef, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import Underline from "@tiptap/extension-underline";
import TextAlign from "@tiptap/extension-text-align";
import { AnimatePresence, motion } from "framer-motion";
import {
  X, Wand2, Send, Copy, RefreshCw, Check, AlertCircle,
  Clock, Zap, Mail, Eye, Edit3
} from "lucide-react";
import { useEmailStore } from "../stores/emailStore";
import TokenBadge from "./TokenBadge";
import { useSettingsStore } from "../stores/settingsStore";
import { useScanStore } from "../stores/scanStore";
import { api } from "../lib/api";

function Toolbar({ editor }) {
  if (!editor) return null;
  const btn = (label, cmd, active) => (
    <button key={label} onClick={cmd} className={active ? "is-active" : ""}>{label}</button>
  );
  return (
    <div className="editor-toolbar">
      {btn("B", () => editor.chain().focus().toggleBold().run(), editor.isActive("bold"))}
      {btn("I", () => editor.chain().focus().toggleItalic().run(), editor.isActive("italic"))}
      {btn("U", () => editor.chain().focus().toggleUnderline().run(), editor.isActive("underline"))}
      <div className="editor-toolbar__sep" />
      {btn("H2", () => editor.chain().focus().toggleHeading({ level: 2 }).run(), editor.isActive("heading", { level: 2 }))}
      {btn("H3", () => editor.chain().focus().toggleHeading({ level: 3 }).run(), editor.isActive("heading", { level: 3 }))}
      {btn("• List", () => editor.chain().focus().toggleBulletList().run(), editor.isActive("bulletList"))}
      <div className="editor-toolbar__sep" />
      <button onClick={() => { const u = window.prompt("URL:"); if (u) editor.chain().focus().setLink({ href: u }).run(); }}>Link</button>
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    queued:     { label: "Queued",     color: "var(--ink3)",  icon: <Clock size={10} /> },
    generating: { label: "Generating", color: "var(--blue)",  icon: <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: "linear" }} style={{ display:"flex" }}><Zap size={10} /></motion.div> },
    ready:      { label: "Ready",      color: "var(--green)", icon: <Check size={10} /> },
    error:      { label: "Error",      color: "var(--red)",   icon: <AlertCircle size={10} /> },
    sent:       { label: "Sent",       color: "var(--accent)",icon: <Mail size={10} /> },
  };
  const s = map[status];
  if (!s) return null;
  return (
    <span style={{ display:"inline-flex", alignItems:"center", gap:4, fontSize:11,
      color:s.color, fontFamily:"var(--font-mono)", background:`${s.color}18`,
      padding:"2px 8px", borderRadius:99, border:`1px solid ${s.color}30` }}>
      {s.icon} {s.label}
    </span>
  );
}

function EmailPreview({ html }) {
  const ref = useRef(null);
  useEffect(() => {
    const iframe = ref.current;
    if (!iframe || !html) return;
    const doc = iframe.contentDocument || iframe.contentWindow?.document;
    if (!doc) return;
    doc.open();
    doc.write(html);
    doc.close();
  }, [html]);

  if (!html) {
    return (
      <div style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center",
        color:"var(--ink3)", fontSize:13, padding:24 }}>
        Generate an email to see the preview.
      </div>
    );
  }

  return (
    <div style={{ flex:1, background:"#f8f9ff", borderRadius:"0 0 8px 8px", overflow:"hidden",
      border:"1px solid var(--border)", borderTop:"none" }}>
      <iframe
        ref={ref}
        title="Email preview"
        style={{ width:"100%", height:"100%", border:"none", display:"block", minHeight:520 }}
        sandbox="allow-same-origin"
      />
    </div>
  );
}

export default function EmailDrawer() {
  const store = useEmailStore();
  const settings = useSettingsStore();
  const { shallowHistory, batchHistory } = useScanStore();
  const { drawerUrl, closeDrawer } = store;
  const [activeTab, setActiveTab] = useState("edit"); // "edit" | "preview"
  const [justSent, setJustSent] = useState(false);

  // Find the scan result for this URL across all history banks
  const scanResult = (() => {
    if (!drawerUrl) return null;
    for (const run of shallowHistory) {
      if (run.result?.url === drawerUrl) return run.result;
    }
    for (const run of batchHistory) {
      const item = run.results?.find(r => r.url === drawerUrl);
      if (item?.result) return { ...item.result, url: drawerUrl };
    }
    return null;
  })();

  const emailData = drawerUrl ? store.getEmail(drawerUrl) : null;
  const prevUrl = useRef(null);
  const externalUpdateRef = useRef(false);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      Link.configure({ openOnClick: false }),
      TextAlign.configure({ types: ["heading", "paragraph"] }),
    ],
    content: "<p>Click <strong>Generate</strong> to create your outreach email.</p>",
    onUpdate: ({ editor }) => {
      if (externalUpdateRef.current) return; // ignore updates we triggered ourselves
      if (drawerUrl) store.setHtmlContent(drawerUrl, editor.getHTML());
    },
  });

  // Sync editor when URL changes or content arrives
  useEffect(() => {
    if (!editor || !drawerUrl) return;
    if (prevUrl.current !== drawerUrl) {
      // URL changed — load stored content
      const stored = store.getEmail(drawerUrl)?.htmlContent;
      externalUpdateRef.current = true;
      editor.commands.setContent(
        stored || "<p>Click <strong>Generate</strong> to create your outreach email.</p>",
        false
      );
      setTimeout(() => { externalUpdateRef.current = false; }, 0);
      prevUrl.current = drawerUrl;
    } else if (emailData?.htmlContent) {
      // Content updated externally (generation finished OR card rebuilt from checkbox)
      const current = editor.getHTML();
      if (current !== emailData.htmlContent) {
        externalUpdateRef.current = true;
        editor.commands.setContent(emailData.htmlContent, false);
        setTimeout(() => { externalUpdateRef.current = false; }, 0);
        // Only auto-switch to preview on fresh generation, not card rebuilds
        if (emailData?.status === "ready") setActiveTab("preview");
      }
    }
  }, [drawerUrl, emailData?.htmlContent]);

  function getAISettings() {
    // Use email-specific provider/model if set, otherwise fall back to audit model
    const provider = settings.emailAiProvider || settings.aiProvider;
    return {
      ai_provider:       provider,
      ollama_base_url:   settings.ollamaBaseUrl,
      ollama_model:      provider === "ollama" ? (settings.emailOllamaModel   || settings.ollamaModel)   : settings.ollamaModel,
      openai_api_key:    settings.openaiApiKey,
      openai_model:      provider === "openai" ? (settings.emailOpenaiModel   || settings.openaiModel)   : settings.openaiModel,
      anthropic_api_key: settings.anthropicApiKey,
      anthropic_model:   provider === "claude" ? (settings.emailAnthropicModel || settings.anthropicModel) : settings.anthropicModel,
      your_name:    settings.yourName,
      your_title:   settings.yourTitle,
      your_email:   settings.yourEmail,
      your_website: settings.yourWebsite,
    };
  }

  // Capture a screenshot of the results summary panel via html2canvas if available
  // Falls back to sending the page screenshot from the scan result
  function generate() {
    if (!drawerUrl || !scanResult) return;
    if (["ready", "error"].includes(emailData?.status)) {
      // Preserve recipient and send history across regeneration
      const preserved = {
        recipientEmail: emailData?.recipientEmail,
        sentAt: emailData?.sentAt,
        checkedIssues: emailData?.checkedIssues,
      };
      store.resetUrl(drawerUrl);
      if (preserved.recipientEmail || preserved.sentAt) {
        useEmailStore.setState(s => ({
          emails: { ...s.emails, [drawerUrl]: { ...(s.emails[drawerUrl] || {}), ...preserved } }
        }));
      }
    }
    // Backend generates the report card HTML from scan data — no screenshot needed here
    store.generate(drawerUrl, scanResult, getAISettings());
  }

  async function send() {
    if (!drawerUrl) return;
    const to = emailData?.recipientEmail?.trim();
    if (!to) return;
    try {
      await api.sendEmail(to, emailData.subject, emailData.htmlContent, {
        gmail_address: settings.gmailAddress,
        gmail_app_password: settings.gmailAppPassword,
        your_name: settings.yourName,
        from_address: settings.fromAddress,
      }, drawerUrl);
      useEmailStore.setState(s => ({
        emails: { ...s.emails, [drawerUrl]: { ...s.emails[drawerUrl], status: "sent", sentAt: new Date().toISOString() } }
      }));
      setJustSent(true);
      setTimeout(() => setJustSent(false), 3000);
    } catch (e) {
      useEmailStore.setState(s => ({
        emails: { ...s.emails, [drawerUrl]: { ...s.emails[drawerUrl], error: e.message, status: "error" } }
      }));
    }
  }

  const isOpen = !!drawerUrl;
  const isBusy = ["generating", "queued"].includes(emailData?.status);
  const hasContent = !!emailData?.htmlContent;
  const wasAlreadySent = !!emailData?.sentAt;  // set by emailStore after successful send

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="email-drawer email-drawer--open"
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "spring", stiffness: 340, damping: 34 }}
        >
          {/* Header */}
          <div className="email-drawer__header">
            <div style={{ display:"flex", flexDirection:"column", flex:1, minWidth:0, gap:4 }}>
              <div style={{ display:"flex", alignItems:"center", gap:8, flexWrap:"wrap" }}>
                <span style={{ fontSize:13, fontWeight:600 }}>Outreach Email</span>
                <StatusPill status={emailData?.status} />
                <TokenBadge tokens={emailData?.tokensTotal} costType="email" />
              </div>
              {drawerUrl && <span className="email-drawer__url">{drawerUrl}</span>}
            </div>
            <div style={{ display:"flex", gap:6, flexShrink:0 }}>
              <button className="btn btn--ghost btn--sm" onClick={generate} disabled={isBusy}>
                {isBusy
                  ? <><div className="spinner" /> {emailData?.status === "queued" ? "Queued…" : "Generating…"}</>
                  : hasContent
                    ? <><RefreshCw size={12} /> Regen</>
                    : <><Wand2 size={12} /> Generate</>}
              </button>
              <button className="btn btn--ghost btn--icon btn--sm" onClick={closeDrawer}>
                <X size={15} />
              </button>
            </div>
          </div>

          {/* Tabs */}
          <div style={{ display:"flex", gap:0, borderBottom:"1px solid var(--border)",
            background:"var(--bg3)", flexShrink:0 }}>
            {[
              { id:"preview", icon:<Eye size={12}/>,    label:"Preview" },
            ].map(tab => (
              <button key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  display:"flex", alignItems:"center", gap:5, padding:"9px 16px",
                  fontSize:12, fontWeight:500,
                  color: "var(--blue)",
                  borderBottom: "2px solid var(--blue)",
                  background: "none", marginBottom:"-1px",
                }}>
                {tab.icon} {tab.label}
              </button>
            ))}
            <div style={{ flex:1 }} />
            <button className="btn btn--ghost btn--sm"
              style={{ margin:"6px 12px" }}
              onClick={() => navigator.clipboard.writeText(emailData?.htmlContent || "")}
              disabled={!hasContent}>
              <Copy size={11} /> Copy HTML
            </button>
          </div>

          {/* Body */}
          <div className="email-drawer__body">
            <AnimatePresence mode="wait">
              {emailData?.status === "error" && (
                <motion.div key="err" className="alert alert--error"
                  initial={{ opacity:0, y:-8 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0 }}>
                  <AlertCircle size={14} /> {emailData.error}
                </motion.div>
              )}
              {isBusy && (
                <motion.div key="busy" className="alert alert--info"
                  initial={{ opacity:0, y:-8 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0 }}>
                  <div className="spinner" />
                  {emailData?.status === "queued"
                    ? "Queued — waiting for previous generation…"
                    : "AI is writing your email with the page screenshot…"}
                </motion.div>
              )}
            </AnimatePresence>

            <div className="field">
              <label>Subject</label>
              <input
                value={emailData?.subject || ""}
                onChange={e => drawerUrl && store.setSubject(drawerUrl, e.target.value)}
                placeholder="Generated subject will appear here"
              />
            </div>

            <EmailPreview html={emailData?.htmlContent} />
          </div>

          {/* Footer */}
          <div className="email-drawer__footer" style={{ flexDirection: "column", gap: 8 }}>
            {wasAlreadySent && (
              <div style={{ fontSize: 11, color: "var(--ink3)", background: "var(--surface)",
                border: "1px solid var(--border)", borderRadius: "var(--radius)",
                padding: "6px 10px", textAlign: "center", width: "100%" }}>
                ⚠ This email was already sent — you can send it again if needed
              </div>
            )}
            <div style={{ display: "flex", gap: 8, width: "100%" }}>
              <input type="email"
                value={emailData?.recipientEmail || ""}
                onChange={e => drawerUrl && store.setRecipient(drawerUrl, e.target.value)}
                placeholder="recipient@company.co.jp"
                style={{ flex:1 }} />
              <button className="btn btn--primary" onClick={send}
                disabled={!hasContent || !emailData?.recipientEmail || justSent}>
                {justSent
                  ? <><Check size={13} /> Sent!</>
                  : <><Send size={13} /> Send</>}
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
