import { create } from "zustand";

type View = "list" | "kanban" | "calendar" | "timeline";

interface ViewState {
  currentView: View;
  setView: (view: View) => void;
}

export const useViewStore = create<ViewState>((set) => ({
  currentView: "list",
  setView: (view) => set({ currentView: view }),
}));
