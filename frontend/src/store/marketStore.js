import { create } from 'zustand'

export const useMarketStore = create((set) => ({
  // Live market data
  marketData: {},
  previousData: {},   // previous snapshot for delta/color computation
  lastUpdated: null,

  // Signals
  activeSignals: [],
  signalHistory: [],

  // Trades
  openTrades: [],
  tradeHistory: [],

  // Predictions
  todayPrediction: null,

  // Bot activity log
  activityLog: [],

  // Heal warnings
  healWarnings: [],

  // System monitor logs (real-time from backend)
  systemLogs: [],

  // Connection status
  wsConnected: false,
  wsError: null,

  // Actions
  setMarketData: (data) => set((state) => ({
    previousData: state.marketData,
    marketData: data,
    lastUpdated: new Date(),
  })),
  setActiveSignals: (signals) => set({ activeSignals: signals }),
  setOpenTrades: (trades) => set({ openTrades: trades }),
  setTodayPrediction: (p) => set({ todayPrediction: p }),

  addActivity: (msg, level = 'INFO') => set((state) => ({
    activityLog: [
      { id: Date.now(), message: msg, level, ts: new Date().toISOString() },
      ...state.activityLog.slice(0, 99),
    ],
  })),

  addHealWarning: (warning) => set((state) => ({
    healWarnings: [
      { id: Date.now(), ...warning },
      ...state.healWarnings.slice(0, 9),
    ],
  })),

  dismissHealWarning: (id) => set((state) => ({
    healWarnings: state.healWarnings.filter(w => w.id !== id),
  })),

  addSystemLog: (entry) => set((state) => ({
    systemLogs: [entry, ...state.systemLogs].slice(0, 500),
  })),

  clearSystemLogs: () => set({ systemLogs: [] }),

  setWsConnected: (connected) => set({ wsConnected: connected }),
  setWsError: (err) => set({ wsError: err }),

  // Update open trade P&L in real time
  updateTradePnl: (trade_id, unrealised_pnl, current_premium) => set((state) => ({
    openTrades: state.openTrades.map(t =>
      t.id === trade_id ? { ...t, unrealised_pnl, current_premium } : t
    ),
  })),
}))