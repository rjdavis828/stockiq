import { create } from 'zustand';

interface Watchlist {
  symbol: string;
  name: string;
}

export interface AlertNotification {
  alertId: number;
  symbol: string;
  message: string;
  triggeredAt: string;
}

interface StoreState {
  watchlist: Watchlist[];
  addWatchlist: (item: Watchlist) => void;
  removeWatchlist: (symbol: string) => void;
  darkMode: boolean;
  toggleDarkMode: () => void;
  pendingAlerts: AlertNotification[];
  addPendingAlert: (n: AlertNotification) => void;
  clearPendingAlerts: () => void;
}

export const useStore = create<StoreState>((set) => ({
  watchlist: [],
  addWatchlist: (item) =>
    set((state) => ({
      watchlist: state.watchlist.some((w) => w.symbol === item.symbol)
        ? state.watchlist
        : [...state.watchlist, item],
    })),
  removeWatchlist: (symbol) =>
    set((state) => ({
      watchlist: state.watchlist.filter((w) => w.symbol !== symbol),
    })),
  darkMode: true,
  toggleDarkMode: () => set((state) => ({ darkMode: !state.darkMode })),
  pendingAlerts: [],
  addPendingAlert: (n) =>
    set((state) => ({ pendingAlerts: [...state.pendingAlerts, n] })),
  clearPendingAlerts: () => set({ pendingAlerts: [] }),
}));
