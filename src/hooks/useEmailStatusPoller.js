/**
 * useEmailStatusPoller
 *
 * Polls /api/email-status every `intervalMs` ms for a list of URLs.
 * On any status change it:
 *   1. Calls onUpdate(url, emailBlock) — for page-level row updates (History, Discover)
 *   2. Calls applyEmailStatusToStore(url, emailBlock) — so EmailDrawer / ResultsPage
 *      also reflect the live status without needing their own polling setup.
 *
 * Silent by design — no console logs, no log spam.
 */
import { useEffect, useRef } from "react";
import { api } from "../lib/api";
import { applyEmailStatusToStore } from "../stores/emailStore";

export function useEmailStatusPoller(urls, onUpdate, intervalMs = 5000) {
  const prevRef = useRef({});
  const timerRef = useRef(null);
  const urlsRef = useRef(urls);

  useEffect(() => {
    urlsRef.current = urls;
  }, [urls]);

  useEffect(() => {
    if (!urls || urls.length === 0) return;

    async function poll() {
      try {
        const statuses = await api.getEmailStatuses(urlsRef.current);
        for (const [url, emailBlock] of Object.entries(statuses)) {
          const prev = prevRef.current[url];
          const prevKey = prev?.status ?? prev?.sent_at ?? null;
          const nextKey = emailBlock?.status ?? emailBlock?.sent_at ?? null;
          if (prevKey !== nextKey) {
            prevRef.current[url] = emailBlock;
            // Update page-level rows (History table, Discover table)
            if (onUpdate) onUpdate(url, emailBlock);
            // Update email drawer / results page store globally
            applyEmailStatusToStore(url, emailBlock);
          }        }
      } catch {
        // Silent — network errors just retry next interval
      }
    }

    poll();
    timerRef.current = setInterval(poll, intervalMs);
    return () => clearInterval(timerRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, onUpdate]);
}
