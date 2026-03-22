const BASE = "/api";

async function post(path, body, signal) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

async function postStream(path, body, onLine, signal) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.error || `HTTP ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed) onLine(JSON.parse(trimmed));
    }
  }
  if (buffer.trim()) onLine(JSON.parse(buffer.trim()));
}

async function postStreamLast(path, body, signal) {
  return new Promise((resolve, reject) => {
    let last = null;
    postStream(path, body, (data) => {
      if (data.cancelled) { reject(new Error("cancelled")); return; }
      last = data;
    }, signal)
      .then(() => last ? resolve(last) : reject(new Error("No result received")))
      .catch(reject);
  });
}

export const api = {
  // taskId is a unique string — backend registers it for cancellation
  async analyzePage(url, settings, taskId, signal, scanMode = "shallow", visionMode = false) {
    return postStreamLast("/analyze", { url, settings, task_id: taskId, scan_mode: scanMode, vision_mode: visionMode }, signal);
  },

  // Tell the backend to cancel a running task immediately
  async cancelTask(taskId) {
    try {
      await fetch(`${BASE}/cancel/${taskId}`, { method: "POST" });
    } catch {}
  },

  async crawl(url, maxPages, signal) {
    return post("/crawl", { url, max_pages: maxPages }, signal);
  },

  async generateEmail(scanResult, settings, dashboardScreenshot, signal) {
    return postStreamLast("/generate-email", {
      scan_result: scanResult,
      settings,
      dashboard_screenshot: dashboardScreenshot || null,
    }, signal);
  },


  async agentChat(messages, scanContext, settings, signal) {
    return post("/agent-chat", { messages, scan_context: scanContext, settings }, signal);
  },

  async health() {
    const res = await fetch("/api/health");
    return res.ok;
  },

  // ── History ───────────────────────────────────────────────────────────────
  async getHistory(page = 1, perPage = 20, sortBy = "scanned_at", sortDir = "desc", filterEmail = "all", filterScoreMin = 0, filterScoreMax = 100) {
    const params = new URLSearchParams({
      page, per_page: perPage,
      sort_by: sortBy, sort_dir: sortDir,
      filter_email: filterEmail,
      filter_score_min: filterScoreMin,
      filter_score_max: filterScoreMax,
    });
    const res = await fetch(`${BASE}/history?${params}`);
    return res.json();
  },

  async checkHistory(url) {
    const res = await fetch(`${BASE}/history/check?url=${encodeURIComponent(url)}`);
    return res.json();
  },

  async getHistoryEntry(url) {
    const res = await fetch(`${BASE}/history/entry?url=${encodeURIComponent(url)}`);
    if (!res.ok) throw new Error("Not found");
    return res.json();
  },

  async toggleResponse(url) {
    const res = await fetch(`${BASE}/history/response?url=${encodeURIComponent(url)}`, { method: "PATCH" });
    return res.json();
  },

  async deleteHistoryEntry(url) {
    const res = await fetch(`${BASE}/history/entry?url=${encodeURIComponent(url)}`, { method: "DELETE" });
    return res.json();
  },

  async saveEmailDraft(url, subject, html) {
    const res = await fetch(
      `${BASE}/history/save-email?url=${encodeURIComponent(url)}&subject=${encodeURIComponent(subject)}`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ html }) }
    );
    return res.json();
  },

  async sendEmail(to, subject, html, settings, url = "") {
    return post("/send-email", { to, subject, html, url, settings });
  },

  async rebuildCard(scanResult, selectedIndices) {
    return post("/rebuild-card", { scan_result: scanResult, selected_issue_indices: selectedIndices });
  },

  // ── Discover ──────────────────────────────────────────────────────────────
  async discoverSearch(keywords, location, limit, onProgress) {
    return new Promise((resolve, reject) => {
      let result = null;
      postStream("/discover/search", { keywords, location, limit }, (event) => {
        if (event.type === "result") { result = event; return; }
        if (event.type === "error") { reject(new Error(event.error)); return; }
        if (onProgress) onProgress(event);
      }).then(() => result ? resolve(result) : reject(new Error("No result received")))
        .catch(reject);
    });
  },
  async getProspects(sessionId, sortBy = "discovered_at", sortDir = "desc", filterStatus = "all", filterHasEmail = "all") {
    const params = new URLSearchParams({ sort_by: sortBy, sort_dir: sortDir, filter_status: filterStatus, filter_has_email: filterHasEmail });
    if (sessionId) params.set("session_id", sessionId);
    const res = await fetch(`${BASE}/discover/prospects?${params}`);
    return res.json();
  },
  async getSessions() {
    const res = await fetch(`${BASE}/discover/sessions`);
    return res.json();
  },
  async updateProspectStatus(website, status) {
    return fetch(`${BASE}/discover/status`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ website, status }) }).then(r => r.json());
  },
  async deleteProspect(website) {
    return fetch(`${BASE}/discover/prospect?website=${encodeURIComponent(website)}`, { method: "DELETE" }).then(r => r.json());
  },
  async updateProspectEmail(website, email) {
    return fetch(`${BASE}/discover/email`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ website, email }) }).then(r => r.json());
  },
};
