import { useCallback, useMemo } from 'react';
import { useWorkspaceStore } from '../store/workspaceStore';
import { useMarketDataStore } from '../store/marketDataStore';
import { indicatorConfigs } from '../components/IndicatorSettings/indicatorConfigs';

// Module-level singleton for chart refs to ensure stability across renders/components
const globalChartRefs = { current: {} };

/**
 * useChart Adapter Hook
 * 
 * This hook replaces the old ChartContext. It provides the same API
 * but bridges to the new Zustand stores (workspaceStore and marketDataStore).
 */
export const useChart = () => {
    const {
        charts,
        setCharts,
        activeChartId,
        setActiveChartId,
        layout,
        setLayout,
        // chartRefs, // Removed from store
        // setChartRef, // Removed from store
        // getChartRef, // Removed from store
        updateChart,
        updateIndicator: storeUpdateIndicator,
        addIndicator: storeAddIndicator,
        removeIndicator: storeRemoveIndicator
    } = useWorkspaceStore();

    // Helper to access refs securely
    const getChartRef = useCallback((id) => {
        return globalChartRefs.current[id];
    }, []);

    // Derived: Active chart object
    const activeChart = useMemo(
        () => charts.find(c => c.id === activeChartId) || charts[0] || {},
        [charts, activeChartId]
    );

    // Derived: Current properties
    const currentSymbol = activeChart.symbol || 'NIFTY 50';
    const currentExchange = activeChart.exchange || 'NSE';
    const currentInterval = activeChart.interval || '1d';

    // ============ CHART HANDLERS ============

    const updateSymbol = useCallback((symbol, exchange = 'NSE') => {
        // Handle both string and object signature if needed, but context defined it as (symbol, exchange)
        // Check usage in main: handleSymbolChange in App.jsx calls setCharts directly.
        // But if components call updateSymbol, we need this.
        updateChart(activeChartId, { symbol, exchange, strategyConfig: null });
    }, [activeChartId, updateChart]);

    const updateInterval = useCallback((interval) => {
        updateChart(activeChartId, { interval });
    }, [activeChartId, updateChart]);

    // ============ INDICATOR HANDLERS ============

    const addIndicator = useCallback((type) => {
        const config = indicatorConfigs[type];
        const defaultSettings = {};

        // Merge defaults from config inputs
        if (config && config.inputs) {
            config.inputs.forEach(input => {
                if (input.default !== undefined) {
                    defaultSettings[input.key] = input.default;
                }
            });
        }

        // Merge defaults from config styles
        if (config && config.style) {
            config.style.forEach(style => {
                if (style.default !== undefined) {
                    defaultSettings[style.key] = style.default;
                }
            });
        }

        // Fallback defaults
        if (!config) {
            if (type === 'sma') Object.assign(defaultSettings, { period: 20, color: '#2196F3' });
            if (type === 'ema') Object.assign(defaultSettings, { period: 20, color: '#FF9800' });
            if (type === 'tpo') Object.assign(defaultSettings, { blockSize: '30m', tickSize: 'auto' });
        }

        const timestamp = Date.now();
        // Generate a random-ish ID (counter not easy here without store state, use random)
        const id = `${type}_${timestamp}_${Math.floor(Math.random() * 1000)}`;

        const newIndicator = {
            id,
            type,
            visible: true,
            ...defaultSettings
        };

        storeAddIndicator(activeChartId, newIndicator);
    }, [activeChartId, storeAddIndicator]);

    const removeIndicator = useCallback((indicatorId) => {
        storeRemoveIndicator(activeChartId, indicatorId);
    }, [activeChartId, storeRemoveIndicator]);

    const toggleIndicatorVisibility = useCallback((indicatorId) => {
        const chart = charts.find(c => c.id === activeChartId);
        if (!chart) return;

        const indicator = chart.indicators.find(ind => ind.id === indicatorId);
        if (indicator) {
            storeUpdateIndicator(activeChartId, indicatorId, { visible: !indicator.visible });
        }
    }, [activeChartId, charts, storeUpdateIndicator]);

    const updateIndicatorSettings = useCallback((indicatorId, newSettings) => {
        storeUpdateIndicator(activeChartId, indicatorId, newSettings);
    }, [activeChartId, storeUpdateIndicator]);

    const setIndicators = useCallback((newIndicators) => {
        updateChart(activeChartId, { indicators: newIndicators });
    }, [activeChartId, updateChart]);

    // ============ COMPARISON SYMBOLS ============

    const addComparisonSymbol = useCallback((symbol, exchange, color) => {
        const chart = charts.find(c => c.id === activeChartId);
        if (!chart) return;

        const current = chart.comparisonSymbols || [];
        const exists = current.find(c => c.symbol === symbol && c.exchange === exchange);
        if (exists) return;

        updateChart(activeChartId, {
            comparisonSymbols: [...current, { symbol, exchange, color }]
        });
    }, [activeChartId, charts, updateChart]);

    const removeComparisonSymbol = useCallback((symbol, exchange) => {
        const chart = charts.find(c => c.id === activeChartId);
        if (!chart) return;

        const current = chart.comparisonSymbols || [];
        updateChart(activeChartId, {
            comparisonSymbols: current.filter(c => !(c.symbol === symbol && c.exchange === exchange))
        });
    }, [activeChartId, charts, updateChart]);

    // ============ STRATEGY CONFIG ============

    const updateStrategyConfig = useCallback((config) => {
        updateChart(activeChartId, { strategyConfig: config });
    }, [activeChartId, updateChart]);

    // ============ MULTI-CHART MANAGEMENT ============

    const addChart = useCallback(() => {
        const newId = Math.max(...charts.map(c => c.id)) + 1;
        const newChart = {
            id: newId,
            symbol: 'NIFTY 50',
            exchange: 'NSE',
            interval: '1d',
            indicators: [],
            comparisonSymbols: [],
            strategyConfig: null
        };
        // storeAddChart not exported nicely, but we have useWorkspaceStore's addChart
        useWorkspaceStore.getState().addChart(newChart);
        return newId;
    }, [charts]);

    const removeChart = useCallback((chartId) => {
        if (charts.length <= 1) return;
        useWorkspaceStore.getState().removeChart(chartId);
    }, [charts]);

    // Compatibility hook return
    return {
        // State
        charts,
        setCharts,
        activeChartId,
        setActiveChartId,
        layout,
        setLayout,
        chartRefs: globalChartRefs, // Return the singleton ref object directly

        // Derived
        activeChart,
        currentSymbol,
        currentExchange,
        currentInterval,

        // Chart handlers
        updateSymbol,
        updateInterval,

        // Indicator handlers
        addIndicator,
        removeIndicator,
        toggleIndicatorVisibility,
        updateIndicatorSettings,
        setIndicators,

        // Comparison symbols
        addComparisonSymbol,
        removeComparisonSymbol,

        // Strategy
        updateStrategyConfig,

        // Multi-chart
        addChart,
        removeChart,
        getChartRef
    };
};
