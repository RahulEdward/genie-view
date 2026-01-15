import React, { useState, useMemo, useCallback } from 'react';
import {
    TrendingUp,
    TrendingDown,
    Flame,
    Filter,
    X,
    ChevronDown,
    Search,
    BarChart2
} from 'lucide-react';
import styles from './MarketScreenerPanel.module.css';

// Preset filter configurations
const PRESETS = [
    { id: 'gainers', label: 'Gainers', icon: TrendingUp, field: 'chgP', operator: '>', value: 2, color: '#26a69a' },
    { id: 'losers', label: 'Losers', icon: TrendingDown, field: 'chgP', operator: '<', value: -2, color: '#ef5350' },
    { id: 'volume', label: 'Volume', icon: Flame, field: 'volume', operator: '>', value: 1000000, color: '#ff9800' },
    { id: 'above1k', label: '>₹1000', icon: BarChart2, field: 'last', operator: '>', value: 1000, color: '#7c4dff' },
];

const FIELDS = [
    { value: 'last', label: 'Last Price' },
    { value: 'chg', label: 'Change' },
    { value: 'chgP', label: 'Change %' },
    { value: 'volume', label: 'Volume' },
];

const OPERATORS = [
    { value: '>', label: '>' },
    { value: '<', label: '<' },
    { value: '>=', label: '>=' },
    { value: '<=', label: '<=' },
    { value: '=', label: '=' },
];

const MarketScreenerPanel = ({
    items = [],
    onSymbolSelect,
    currentSymbol,
    currentExchange = 'NSE'
}) => {
    const [activePreset, setActivePreset] = useState(null);
    const [customFilter, setCustomFilter] = useState({
        field: 'chgP',
        operator: '>',
        value: ''
    });
    const [showCustom, setShowCustom] = useState(false);
    const [sortConfig, setSortConfig] = useState({ key: 'chgP', direction: 'desc' });

    // Filter items based on active filter
    const filteredItems = useMemo(() => {
        // Get stock items only (exclude section markers)
        const stockItems = items.filter(item =>
            typeof item !== 'string' && item.symbol
        );

        if (!activePreset && !customFilter.value) {
            return stockItems;
        }

        let filter = null;
        if (activePreset) {
            const preset = PRESETS.find(p => p.id === activePreset);
            if (preset) {
                filter = { field: preset.field, operator: preset.operator, value: preset.value };
            }
        } else if (customFilter.value) {
            filter = { ...customFilter, value: parseFloat(customFilter.value) };
        }

        if (!filter) return stockItems;

        return stockItems.filter(item => {
            const value = parseFloat(item[filter.field]) || 0;
            switch (filter.operator) {
                case '>': return value > filter.value;
                case '<': return value < filter.value;
                case '>=': return value >= filter.value;
                case '<=': return value <= filter.value;
                case '=': return Math.abs(value - filter.value) < 0.01;
                default: return true;
            }
        });
    }, [items, activePreset, customFilter]);

    // Sort filtered items
    const sortedItems = useMemo(() => {
        if (!sortConfig.key) return filteredItems;

        return [...filteredItems].sort((a, b) => {
            // Special case for symbol - use string comparison
            if (sortConfig.key === 'symbol') {
                const aValue = (a.symbol || '').toUpperCase();
                const bValue = (b.symbol || '').toUpperCase();
                const result = aValue.localeCompare(bValue);
                return sortConfig.direction === 'asc' ? result : -result;
            }

            // Numeric comparison for other fields
            const aValue = parseFloat(a[sortConfig.key]) || 0;
            const bValue = parseFloat(b[sortConfig.key]) || 0;

            if (sortConfig.direction === 'asc') {
                return aValue - bValue;
            }
            return bValue - aValue;
        });
    }, [filteredItems, sortConfig]);

    const handlePresetClick = useCallback((presetId) => {
        if (activePreset === presetId) {
            setActivePreset(null);
        } else {
            setActivePreset(presetId);
            setShowCustom(false);
            setCustomFilter(prev => ({ ...prev, value: '' }));
        }
    }, [activePreset]);

    const handleCustomApply = useCallback(() => {
        if (customFilter.value) {
            setActivePreset(null);
        }
    }, [customFilter.value]);

    const handleClearFilter = useCallback(() => {
        setActivePreset(null);
        setCustomFilter(prev => ({ ...prev, value: '' }));
    }, []);

    const handleSort = useCallback((key) => {
        setSortConfig(prev => ({
            key,
            direction: prev.key === key && prev.direction === 'desc' ? 'asc' : 'desc'
        }));
    }, []);

    const formatValue = (value, field) => {
        if (value === undefined || value === null) return '--';
        const num = parseFloat(value);
        if (isNaN(num)) return '--';

        if (field === 'volume') {
            if (num >= 10000000) return `${(num / 10000000).toFixed(2)}Cr`;
            if (num >= 100000) return `${(num / 100000).toFixed(2)}L`;
            if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
            return num.toString();
        }
        return num.toFixed(2);
    };

    const activeFilterLabel = useMemo(() => {
        if (activePreset) {
            const preset = PRESETS.find(p => p.id === activePreset);
            return preset ? `${preset.label}: ${FIELDS.find(f => f.value === preset.field)?.label} ${preset.operator} ${preset.value}` : '';
        }
        if (customFilter.value) {
            const field = FIELDS.find(f => f.value === customFilter.field);
            return `${field?.label} ${customFilter.operator} ${customFilter.value}`;
        }
        return null;
    }, [activePreset, customFilter]);

    return (
        <div className={styles.container}>
            {/* Header */}
            <div className={styles.header}>
                <div className={styles.headerTitle}>
                    <Search size={16} />
                    <span>Market Screener</span>
                </div>
            </div>

            {/* Quick Filters */}
            <div className={styles.presetsSection}>
                <div className={styles.sectionLabel}>Quick Filters</div>
                <div className={styles.presetGrid}>
                    {PRESETS.map(preset => {
                        const Icon = preset.icon;
                        const isActive = activePreset === preset.id;
                        return (
                            <button
                                key={preset.id}
                                className={`${styles.presetBtn} ${isActive ? styles.presetActive : ''}`}
                                onClick={() => handlePresetClick(preset.id)}
                                style={isActive ? { borderColor: preset.color, color: preset.color } : {}}
                            >
                                <Icon size={14} />
                                <span>{preset.label}</span>
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Custom Filter */}
            <div className={styles.customSection}>
                <button
                    className={styles.customToggle}
                    onClick={() => setShowCustom(!showCustom)}
                >
                    <Filter size={14} />
                    <span>Custom Filter</span>
                    <ChevronDown size={14} className={showCustom ? styles.rotated : ''} />
                </button>

                {showCustom && (
                    <div className={styles.customBuilder}>
                        <select
                            value={customFilter.field}
                            onChange={(e) => setCustomFilter(prev => ({ ...prev, field: e.target.value }))}
                            className={styles.select}
                        >
                            {FIELDS.map(f => (
                                <option key={f.value} value={f.value}>{f.label}</option>
                            ))}
                        </select>
                        <select
                            value={customFilter.operator}
                            onChange={(e) => setCustomFilter(prev => ({ ...prev, operator: e.target.value }))}
                            className={styles.select}
                        >
                            {OPERATORS.map(op => (
                                <option key={op.value} value={op.value}>{op.label}</option>
                            ))}
                        </select>
                        <input
                            type="number"
                            value={customFilter.value}
                            onChange={(e) => setCustomFilter(prev => ({ ...prev, value: e.target.value }))}
                            onKeyDown={(e) => e.key === 'Enter' && handleCustomApply()}
                            placeholder="Value"
                            className={styles.input}
                        />
                        <button
                            className={styles.applyBtn}
                            onClick={handleCustomApply}
                            disabled={!customFilter.value}
                        >
                            Apply
                        </button>
                    </div>
                )}
            </div>

            {/* Active Filter Display */}
            {activeFilterLabel && (
                <div className={styles.activeFilter}>
                    <span>{activeFilterLabel}</span>
                    <button onClick={handleClearFilter} className={styles.clearBtn}>
                        <X size={14} />
                    </button>
                </div>
            )}

            {/* Results Header */}
            <div className={styles.resultsHeader}>
                <span
                    className={styles.colSymbol}
                    onClick={() => handleSort('symbol')}
                >
                    Symbol {sortConfig.key === 'symbol' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                </span>
                <span
                    className={styles.colLast}
                    onClick={() => handleSort('last')}
                >
                    Last {sortConfig.key === 'last' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                </span>
                <span
                    className={styles.colChgP}
                    onClick={() => handleSort('chgP')}
                >
                    Chg% {sortConfig.key === 'chgP' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                </span>
            </div>

            {/* Results List */}
            <div className={styles.resultsList}>
                {sortedItems.length === 0 ? (
                    <div className={styles.emptyState}>
                        <Filter size={24} />
                        <p>{activeFilterLabel ? 'No symbols match the filter' : 'Apply a filter to see results'}</p>
                    </div>
                ) : (
                    <>
                        <div className={styles.resultCount}>
                            Found: {sortedItems.length} symbol{sortedItems.length !== 1 ? 's' : ''}
                        </div>
                        {sortedItems.map((item, idx) => {
                            const chgP = parseFloat(item.chgP) || 0;
                            const isUp = chgP >= 0;
                            const isActive = currentSymbol === item.symbol && currentExchange === (item.exchange || 'NSE');

                            return (
                                <div
                                    key={`${item.symbol}-${item.exchange}-${idx}`}
                                    className={`${styles.resultItem} ${isActive ? styles.resultActive : ''}`}
                                    onClick={() => onSymbolSelect?.({ symbol: item.symbol, exchange: item.exchange || 'NSE' })}
                                >
                                    <span className={styles.itemSymbol}>{item.symbol}</span>
                                    <span className={styles.itemLast}>{formatValue(item.last, 'last')}</span>
                                    <span className={`${styles.itemChgP} ${isUp ? styles.up : styles.down}`}>
                                        {isUp ? '+' : ''}{formatValue(item.chgP, 'chgP')}%
                                    </span>
                                </div>
                            );
                        })}
                    </>
                )}
            </div>
        </div>
    );
};

export default React.memo(MarketScreenerPanel);
