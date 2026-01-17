import { create } from 'zustand';
import { persist, createJSONStorage, subscribeWithSelector } from 'zustand/middleware';

// Helper to safely parse JSON
const safeParseJSON = (value, fallback) => {
    if (!value) return fallback;
    try {
        return JSON.parse(value);
    } catch (error) {
        console.error('Failed to parse JSON from localStorage:', error);
        return fallback;
    }
};

// Migration function (adapted from App.jsx)
const migrateIndicators = (indicators) => {
    if (Array.isArray(indicators)) return indicators;

    const migrated = [];
    const timestamp = Date.now();
    let counter = 0;

    Object.entries(indicators || {}).forEach(([type, config]) => {
        if (config === false) return;

        const base = {
            id: `${type}_${timestamp}_${counter++}`,
            type: type,
            visible: true
        };

        if (config === true) {
            if (type === 'sma') Object.assign(base, { period: 20, color: '#2196F3' });
            if (type === 'ema') Object.assign(base, { period: 20, color: '#FF9800' });
            migrated.push(base);
        } else if (typeof config === 'object' && config !== null) {
            if (config.enabled === false) return;
            const { enabled, ...settings } = config;
            Object.assign(base, settings);
            if (settings.hidden) {
                base.visible = false;
                delete base.hidden;
            }
            migrated.push(base);
        }
    });
    return migrated;
};

// Load initial state from OLD storage if new storage is empty
const loadInitialState = () => {
    const oldData = safeParseJSON(localStorage.getItem('tv_saved_layout'), null);

    if (oldData) {
        // Perform migration on old data
        const migratedCharts = (oldData.charts || []).map(chart => ({
            ...chart,
            // Fix invalid default NIFTY 50
            symbol: chart.symbol === 'NIFTY 50' ? 'NIFTY' : chart.symbol,
            exchange: (chart.symbol === 'NIFTY 50' || chart.symbol === 'NIFTY') ? 'NSE_INDEX' : chart.exchange,
            indicators: migrateIndicators(chart.indicators || []).map(ind => {
                // Fix 'classic' pivot type bug
                if (ind.type === 'classic') {
                    return { ...ind, type: 'pivotPoints', pivotType: 'classic' };
                }
                return ind;
            })
        }));

        return {
            layout: oldData.layout || '1',
            activeChartId: migratedCharts[0]?.id || 1, // Default to first chart logic
            charts: migratedCharts.length > 0 ? migratedCharts : [
                { id: 1, symbol: 'NIFTY', exchange: 'NSE_INDEX', interval: 'D', indicators: [] }
            ],
            chartRefs: {}
        };
    }

    // Fallback default
    return {
        layout: '1',
        activeChartId: 1,
        charts: [
            { id: 1, symbol: 'NIFTY', exchange: 'NSE_INDEX', interval: 'D', indicators: [] }
        ],
        chartRefs: {} // Non-persisted refs
    };
};

export const useWorkspaceStore = create(
    subscribeWithSelector(
        persist(
            (set, get) => ({
                ...loadInitialState(),

                // Actions
                setLayout: (layout) => set({ layout }),

                setActiveChartId: (idOrFn) => set((state) => ({
                    activeChartId: typeof idOrFn === 'function' ? idOrFn(state.activeChartId) : idOrFn
                })),

                setCharts: (chartsOrFn) => set((state) => ({
                    charts: typeof chartsOrFn === 'function' ? chartsOrFn(state.charts) : chartsOrFn
                })),

                addChart: (newChart) => set((state) => ({
                    charts: [...state.charts, newChart],
                    activeChartId: newChart.id
                })),

                removeChart: (id) => set((state) => {
                    const newCharts = state.charts.filter(c => c.id !== id);
                    let newActiveId = state.activeChartId;
                    // If removing active chart, select the first one available
                    if (state.activeChartId === id) {
                        newActiveId = newCharts[0]?.id || null;
                    }
                    return { charts: newCharts, activeChartId: newActiveId };
                }),

                updateChart: (id, updates) => set((state) => ({
                    charts: state.charts.map(c => c.id === id ? { ...c, ...updates } : c)
                })),

                // Helper to update specific indicator
                updateIndicator: (chartId, indicatorId, settings) => set((state) => ({
                    charts: state.charts.map(chart => {
                        if (chart.id !== chartId) return chart;
                        return {
                            ...chart,
                            indicators: chart.indicators.map(ind =>
                                ind.id === indicatorId ? { ...ind, ...settings } : ind
                            )
                        };
                    })
                })),

                addIndicator: (chartId, indicator) => set((state) => ({
                    charts: state.charts.map(chart => {
                        if (chart.id !== chartId) return chart;
                        return { ...chart, indicators: [...chart.indicators, indicator] };
                    })
                })),

                removeIndicator: (chartId, indicatorId) => set((state) => ({
                    charts: state.charts.map(chart => {
                        if (chart.id !== chartId) return chart;
                        return {
                            ...chart,
                            indicators: chart.indicators.filter(ind => ind.id !== indicatorId)
                        };
                    })
                })),

                // Ref Handling
                setChartRef: (id, ref) => set((state) => ({
                    chartRefs: { ...state.chartRefs, [id]: ref }
                })),

                getChartRef: (id) => {
                    return get().chartRefs[id];
                },

                // Cloud Sync: Hydrate store directly from cloud data
                // This allows updating the store without requiring a remount
                setFromCloud: (cloudLayoutData) => set((state) => {
                    if (!cloudLayoutData) return state;

                    // Parse if string (from localStorage format)
                    let layoutData;
                    try {
                        layoutData = typeof cloudLayoutData === 'string'
                            ? JSON.parse(cloudLayoutData)
                            : cloudLayoutData;
                    } catch (e) {
                        console.error('[WorkspaceStore] Failed to parse cloud data:', e);
                        return state;
                    }

                    // Validate structure
                    if (!layoutData || typeof layoutData !== 'object') {
                        return state;
                    }

                    // Migrate charts (same logic as loadInitialState)
                    const migratedCharts = (layoutData.charts || []).map(chart => ({
                        ...chart,
                        // Fix invalid default NIFTY 50
                        symbol: chart.symbol === 'NIFTY 50' ? 'NIFTY' : chart.symbol,
                        exchange: (chart.symbol === 'NIFTY 50' || chart.symbol === 'NIFTY')
                            ? 'NSE_INDEX' : chart.exchange,
                        indicators: migrateIndicators(chart.indicators || []).map(ind => {
                            // Fix 'classic' pivot type bug
                            if (ind.type === 'classic') {
                                return { ...ind, type: 'pivotPoints', pivotType: 'classic' };
                            }
                            return ind;
                        })
                    }));

                    // Only update if we have valid data
                    if (migratedCharts.length === 0) {
                        return state;
                    }

                    console.log('[WorkspaceStore] Hydrating from cloud:', {
                        layout: layoutData.layout,
                        chartsCount: migratedCharts.length
                    });

                    return {
                        layout: layoutData.layout || state.layout,
                        activeChartId: layoutData.activeChartId || migratedCharts[0]?.id || state.activeChartId,
                        charts: migratedCharts
                    };
                })
            }),
            {
                name: 'openalgo-workspace-storage', // New storage key
                storage: createJSONStorage(() => localStorage),
                version: 1, // Add versioning
                migrate: (persistedState, version) => {
                    let state = persistedState;
                    if (version === 0) {
                        // Migration for version 0 (initial release with NIFTY 50 bug)
                        state.charts = (state.charts || []).map(chart => ({
                            ...chart,
                            symbol: chart.symbol === 'NIFTY 50' ? 'NIFTY' : chart.symbol,
                            exchange: (chart.symbol === 'NIFTY 50' || chart.symbol === 'NIFTY') ? 'NSE_INDEX' : chart.exchange
                        }));
                    }
                    return state;
                },
                partialize: (state) => ({
                    charts: state.charts,
                    layout: state.layout,
                    activeChartId: state.activeChartId
                }),
                // Add extra actions to the store for ref management - wait, actions are in the create callback
            }
        )
    ));

