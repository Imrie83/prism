import { create } from "zustand";

/**
 * discoverStore — holds all Discover page state that should survive tab switches.
 *
 * NOT persisted to localStorage (no `persist` middleware) — state lives for the
 * duration of the browser session, just like scanStore. If the user refreshes the
 * page, state resets, which is fine.
 */
export const useDiscoverStore = create((set, get) => ({
  // Search form
  keywords: "",
  location: "",
  limit: 120,

  // Search in-progress state
  searching: false,
  searchError: null,
  searchStats: null,
  searchProgress: null,   // { phase, scrolled, detailed, total, withWebsite, keyword, lastName }

  // Sessions
  sessions: [],
  activeSession: null,

  // Results (current page of records from the backend)
  records: [],
  loading: false,

  // Pagination
  page: 1,

  // Selection — intentionally kept in store so it survives tab switch too
  selected: [],   // array of website URLs (Set can't be stored in Zustand easily)

  // Scan in-progress
  scanningUrl: null,

  // UI toggles
  showFilters: false,
  showSuggestions: false,

  // Actions
  set: (partial) => set(partial),
  setField: (key, value) => set({ [key]: value }),

  // Selection helpers
  toggleSelect: (website) => {
    const { selected } = get();
    const s = new Set(selected);
    if (s.has(website)) s.delete(website); else s.add(website);
    set({ selected: [...s] });
  },
  toggleSelectAll: (pageUrls) => {
    const { selected } = get();
    const s = new Set(selected);
    const allSelected = pageUrls.every(u => s.has(u));
    if (allSelected) pageUrls.forEach(u => s.delete(u));
    else pageUrls.forEach(u => s.add(u));
    set({ selected: [...s] });
  },
  clearSelected: () => set({ selected: [] }),
  removeFromSelected: (website) => {
    set(state => ({ selected: state.selected.filter(u => u !== website) }));
  },

  // Update a single record in-place (e.g. after scan status changes)
  updateRecord: (website, patch) => {
    set(state => ({
      records: state.records.map(r => r.website === website ? { ...r, ...patch } : r),
    }));
  },

  // Remove a record (after delete)
  removeRecord: (website) => {
    set(state => ({
      records: state.records.filter(r => r.website !== website),
      selected: state.selected.filter(u => u !== website),
    }));
  },
}));
