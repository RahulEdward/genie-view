import { create } from 'zustand';

// Market Data Store
// Stores real-time data for symbols.
// This allows any component to subscribe to price updates without prop drilling.

export const useMarketDataStore = create((set, get) => ({
    // Map of symbolKey -> { ltp, chg, chgP, volume, ... }
    // keys are usually "SYMBOL:EXCHANGE"
    tickerData: {},

    // Set of subscriptions (symbol keys)
    subscriptions: new Set(),

    // Actions
    updateTicker: (symbol, exchange, data) => set((state) => {
        const key = `${symbol}:${exchange || 'NSE'}`;
        const oldData = state.tickerData[key] || {};

        // Only update if changed (optimization)
        if (oldData.ltp === data.ltp && oldData.volume === data.volume) {
            return state;
        }

        return {
            tickerData: {
                ...state.tickerData,
                [key]: {
                    ...oldData,
                    ...data,
                    lastUpdated: Date.now()
                }
            }
        };
    }),

    // Batch update for performance (e.g. from WebSocket batch messages)
    updateTickers: (updates) => set((state) => {
        const newTickerData = { ...state.tickerData };
        let hasChanges = false;

        updates.forEach(({ symbol, exchange, data }) => {
            const key = `${symbol}:${exchange || 'NSE'}`;
            // Basic check
            if (newTickerData[key]?.ltp !== data.ltp) {
                newTickerData[key] = {
                    ...(newTickerData[key] || {}),
                    ...data,
                    lastUpdated: Date.now()
                };
                hasChanges = true;
            }
        });

        if (!hasChanges) return state;
        return { tickerData: newTickerData };
    }),

    getTicker: (symbol, exchange) => {
        const key = `${symbol}:${exchange || 'NSE'}`;
        return get().tickerData[key];
    }
}));
