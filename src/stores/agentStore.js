import { create } from "zustand";

export const useAgentStore = create((set) => ({
  messages: [], // [{ role: "user"|"assistant", content: string }]
  status: "idle", // "idle" | "thinking"
  isOpen: false,

  setOpen: (open) => set({ isOpen: open }),
  toggleOpen: () => set((s) => ({ isOpen: !s.isOpen })),

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  setStatus: (status) => set({ status }),

  clearHistory: () => set({ messages: [], status: "idle" }),
}));
