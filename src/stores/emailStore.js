import { create } from "zustand";
import { api } from "../lib/api";

async function saveDraftToDB(url, subject, html) {
  try {
    await fetch(`/api/history/save-email?url=${encodeURIComponent(url)}&subject=${encodeURIComponent(subject)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ html }),
    });
  } catch (e) {
    console.warn("[emailStore] draft save failed:", e.message);
  }
}

// emails: { [url]: { status, subject, htmlContent, error, recipientEmail, tokens, generationCount } }
// tokens accumulates across all re-generations for that URL

export const useEmailStore = create((set, get) => ({
  emails: {},
  drawerUrl: null,

  getEmail: (url) => get().emails[url] || null,
  openDrawerFor: (url) => set({ drawerUrl: url }),
  closeDrawer: () => set({ drawerUrl: null }),

  setRecipient: (url, email) =>
    set(s => ({ emails: { ...s.emails, [url]: { ...(s.emails[url] || {}), recipientEmail: email } } })),
  setSubject: (url, subject) =>
    set(s => ({ emails: { ...s.emails, [url]: { ...(s.emails[url] || {}), subject } } })),
  setHtmlContent: (url, html) =>
    set(s => ({ emails: { ...s.emails, [url]: { ...(s.emails[url] || {}), htmlContent: html } } })),

  generate: async (url, scanResult, aiSettings) => {
    const { emails } = get();
    if (["generating", "queued"].includes(emails[url]?.status)) return;

    set(s => ({ emails: { ...s.emails, [url]: { ...(s.emails[url] || {}), status: "queued", error: null } } }));
    await new Promise(r => setTimeout(r, 50));
    set(s => ({ emails: { ...s.emails, [url]: { ...s.emails[url], status: "generating" } } }));

    try {
      const data = await api.generateEmail(scanResult, aiSettings, null);
      set(s => {
        const existing = s.emails[url] || {};
        const prevTokens = existing.tokensTotal || null;
        const newTokens  = data._tokens || null;

        // Accumulate tokens across re-generations
        const accumulated = (() => {
          if (!newTokens) return prevTokens;
          if (!prevTokens) return { ...newTokens, generationCount: 1 };
          return {
            ...newTokens,
            prompt_tokens:     (prevTokens.prompt_tokens     || 0) + (newTokens.prompt_tokens     || 0),
            completion_tokens: (prevTokens.completion_tokens || 0) + (newTokens.completion_tokens || 0),
            total_tokens:      (prevTokens.total_tokens      || 0) + (newTokens.total_tokens      || 0),
            generationCount:   (prevTokens.generationCount   || 1) + 1,
          };
        })();

        return {
          emails: {
            ...s.emails,
            [url]: {
              ...existing,
              status: "ready",
              subject: data.subject,
              htmlContent: data.html,
              tokensLast:  newTokens,    // last generation only
              tokensTotal: accumulated,  // cumulative
            },
          },
        };
      });
      // Save draft to DB immediately — don't wait for send
      saveDraftToDB(url, data.subject, data.html);
    } catch (e) {
      set(s => ({ emails: { ...s.emails, [url]: { ...s.emails[url], status: "error", error: e.message } } }));
    }
  },

  resetUrl: (url) =>
    set(s => { const next = { ...s.emails }; delete next[url]; return { emails: next }; }),

  resetAll: () => set({ emails: {}, drawerUrl: null }),
}));
