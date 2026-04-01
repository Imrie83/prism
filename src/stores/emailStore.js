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
// emailBatchQueue: [url] — URLs queued for batch email generation
// tokens accumulates across all re-generations for that URL

export const useEmailStore = create((set, get) => ({
  emails: {},
  drawerUrl: null,
  emailBatchQueue: [],

  getEmail: (url) => get().emails[url] || null,
  openDrawerFor: (url) => set({ drawerUrl: url }),
  closeDrawer: () => set({ drawerUrl: null }),

  setRecipient: (url, email) =>
    set(s => ({ emails: { ...s.emails, [url]: { ...(s.emails[url] || {}), recipientEmail: email } } })),
  setSubject: (url, subject) =>
    set(s => ({ emails: { ...s.emails, [url]: { ...(s.emails[url] || {}), subject } } })),
  setHtmlContent: (url, html) =>
    set(s => ({ emails: { ...s.emails, [url]: { ...(s.emails[url] || {}), htmlContent: html } } })),
  setCheckedIssues: (url, indices) =>
    set(s => ({ emails: { ...s.emails, [url]: { ...(s.emails[url] || {}), checkedIssues: indices } } })),

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
        const newTokens = data._tokens || null;

        // Accumulate tokens across re-generations
        const accumulated = (() => {
          if (!newTokens) return prevTokens;
          if (!prevTokens) return { ...newTokens, generationCount: 1 };
          return {
            ...newTokens,
            prompt_tokens: (prevTokens.prompt_tokens || 0) + (newTokens.prompt_tokens || 0),
            completion_tokens: (prevTokens.completion_tokens || 0) + (newTokens.completion_tokens || 0),
            total_tokens: (prevTokens.total_tokens || 0) + (newTokens.total_tokens || 0),
            generationCount: (prevTokens.generationCount || 1) + 1,
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
              tokensLast: newTokens, // last generation only
              tokensTotal: accumulated, // cumulative
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

  // ── Email batch queue ──────────────────────────────────────────────────────

  addToEmailBatch: (url) => {
    const { emailBatchQueue } = get();
    if (!emailBatchQueue.includes(url)) {
      set({ emailBatchQueue: [...emailBatchQueue, url] });
    }
  },

  removeFromEmailBatch: (url) =>
    set(s => ({ emailBatchQueue: s.emailBatchQueue.filter(u => u !== url) })),

  clearEmailBatch: () => set({ emailBatchQueue: [] }),

  isInEmailBatch: (url) => get().emailBatchQueue.includes(url),

  executeBatch: async (getScanResult, aiSettings) => {
    const { emailBatchQueue } = get();
    if (!emailBatchQueue.length) return;

    // Mark all queued URLs as generating
    set(s => {
      const next = { ...s.emails };
      for (const url of emailBatchQueue) {
        next[url] = { ...(next[url] || {}), status: "generating", error: null };
      }
      return { emails: next };
    });

    // Build items list — each needs the scan result
    const items = [];
    const validUrls = [];
    for (const url of emailBatchQueue) {
      const scanResult = getScanResult(url);
      if (!scanResult) continue;
      items.push({ scan_result: scanResult });
      validUrls.push(url);
    }

    try {
      const { api } = await import("../lib/api");
      const data = await api.batchGenerateEmail(items, aiSettings);
      const results = data?.results || {};

      set(s => {
        const next = { ...s.emails };
        for (const url of validUrls) {
          const result = results[url];
          if (!result || result.error) {
            next[url] = { ...(next[url] || {}), status: "error", error: result?.error || "batch failed" };
            continue;
          }
          const existing = next[url] || {};
          const prevTokens = existing.tokensTotal || null;
          const newTokens = result._tokens || null;
          const accumulated = newTokens
            ? prevTokens
              ? { ...newTokens, prompt_tokens: (prevTokens.prompt_tokens||0)+(newTokens.prompt_tokens||0), completion_tokens: (prevTokens.completion_tokens||0)+(newTokens.completion_tokens||0), total_tokens: (prevTokens.total_tokens||0)+(newTokens.total_tokens||0), generationCount: (prevTokens.generationCount||1)+1 }
              : { ...newTokens, generationCount: 1 }
            : prevTokens;

          next[url] = { ...existing, status: "ready", subject: result.subject, htmlContent: result.html, tokensLast: newTokens, tokensTotal: accumulated };
          // Save draft to DB
          saveDraftToDB(url, result.subject, result.html);
        }
        return { emails: next };
      });
    } catch (e) {
      set(s => {
        const next = { ...s.emails };
        for (const url of validUrls) {
          next[url] = { ...(next[url] || {}), status: "error", error: e.message };
        }
        return { emails: next };
      });
    }

    set({ emailBatchQueue: [] });
  },
}));

// Standalone action — callable outside React (e.g. from polling hook)
// Merges a fresh email block from the DB into the store without clobbering
// an actively generating email or regressing a sent status.
export function applyEmailStatusToStore(url, emailBlock) {
  if (!emailBlock) return;
  const store = useEmailStore.getState();
  const existing = store.emails[url] || {};
  if (["generating", "queued"].includes(existing.status)) return;
  const sentAt = emailBlock.sent_at;
  const scheduled = emailBlock.status === "scheduled";
  const patch = {};
  if (sentAt && existing.status !== "sent") patch.status = "sent";
  else if (scheduled && !["sent", "generating", "ready"].includes(existing.status)) patch.status = "scheduled";
  if (emailBlock.recipient && !existing.recipientEmail) patch.recipientEmail = emailBlock.recipient;
  if (Object.keys(patch).length === 0) return;
  useEmailStore.setState(s => ({
    emails: { ...s.emails, [url]: { ...s.emails[url], ...patch } },
  }));
}
