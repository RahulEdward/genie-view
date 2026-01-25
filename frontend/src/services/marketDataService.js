/**
 * Market Data Service
 * Handles historical data, quotes, and symbol search
 * Uses backend APIs for all market data operations
 */

import { callBackendAPI } from './apiService';
import logger from '../utils/logger';

// Cache for historical data
const historicalDataCache = new Map();
const CACHE_TTL_MS = 60000; // 1 minute cache

/**
 * Check if cache entry is still valid
 */
const isCacheValid = (cacheEntry) => {
    if (!cacheEntry) return false;
    return Date.now() - cacheEntry.timestamp < CACHE_TTL_MS;
};

/**
 * Get Historical OHLC Data
 * @param {string} symbol - Symbol name
 * @param {string} exchange - Exchange (NSE, BSE, NFO, etc.)
 * @param {string} interval - Time interval (1m, 5m, 15m, 1h, 1d, etc.)
 * @param {string} startDate - Start date in YYYY-MM-DD format
 * @param {string} endDate - End date in YYYY-MM-DD format
 * @returns {Promise<Array>} Array of OHLC candles
 */
export const getHistoricalData = async (symbol, exchange, interval, startDate, endDate) => {
    console.log('[getHistoricalData] Called:', { symbol, exchange, interval, startDate, endDate });
    const cacheKey = `${symbol}:${exchange}:${interval}:${startDate}:${endDate}`;

    // Check cache first
    const cached = historicalDataCache.get(cacheKey);
    if (isCacheValid(cached)) {
        logger.debug('[MarketData] Using cached historical data:', cacheKey);
        console.log('[getHistoricalData] Using cache:', cached.data.length, 'candles');
        return cached.data;
    }

    try {
        logger.debug('[MarketData] Fetching historical data:', { symbol, exchange, interval, startDate, endDate });

        const data = await callBackendAPI('/history', {
            symbol,
            exchange,
            interval,
            start_date: startDate,
            end_date: endDate
        });

        console.log('[getHistoricalData] Raw response:', data?.length || 0, 'items');

        const validData = Array.isArray(data) ? data : [];

        // Transform for Lightweight Charts
        const transformedData = validData.map(item => ({
            time: item.timestamp, // Map timestamp to time
            open: Number(item.open),
            high: Number(item.high),
            low: Number(item.low),
            close: Number(item.close),
            volume: Number(item.volume)
        }));

        console.log('[getHistoricalData] Transformed:', transformedData.length, 'candles');

        // Cache the result
        historicalDataCache.set(cacheKey, {
            data: transformedData,
            timestamp: Date.now()
        });

        // Limit cache size (keep last 50 entries)
        if (historicalDataCache.size > 50) {
            const firstKey = historicalDataCache.keys().next().value;
            historicalDataCache.delete(firstKey);
        }

        return transformedData;
    } catch (error) {
        console.error('[getHistoricalData] Error:', error.message);
        logger.error('[MarketData] Historical data error:', error.message);

        // Return cached data if available (even if stale)
        if (cached) {
            logger.warn('[MarketData] Returning stale cache due to error');
            return cached.data;
        }

        return [];
    }
};

/**
 * Get Current Quote for a symbol
 * @param {string} symbol - Symbol name
 * @param {string} exchange - Exchange
 * @returns {Promise<Object|null>} Quote data with LTP, change, volume, etc.
 */
export const getQuote = async (symbol, exchange) => {
    try {
        logger.debug('[MarketData] Fetching quote:', { symbol, exchange });

        const data = await callBackendAPI('/quotes', { symbol, exchange });
        return data;
    } catch (error) {
        logger.error('[MarketData] Quote error:', error.message);
        return null;
    }
};

/**
 * Get Batch Quotes for multiple symbols
 * @param {Array<{symbol: string, exchange: string}>} symbols - Array of symbol objects
 * @returns {Promise<Array>} Array of quote objects
 */
export const getBatchQuotes = async (symbols) => {
    console.log('[getBatchQuotes] Called with', symbols.length, 'symbols');
    try {
        logger.debug('[MarketData] Fetching batch quotes:', { count: symbols.length });

        const data = await callBackendAPI('/quotes/batch', { symbols });

        console.log('[getBatchQuotes] Raw response:', data);

        if (data && !Array.isArray(data) && typeof data === 'object') {
            const result = Object.values(data);
            console.log('[getBatchQuotes] Converted to array:', result.length, 'items');
            return result;
        }

        console.log('[getBatchQuotes] Returning data as-is:', data?.length || 0, 'items');
        return data || [];
    } catch (error) {
        console.error('[getBatchQuotes] Error:', error.message);
        logger.error('[MarketData] Batch quotes error:', error.message);
        return [];
    }
};

/**
 * Search Symbols across exchanges
 * @param {string} query - Search query
 * @param {string} exchange - Optional: filter by exchange
 * @returns {Promise<Array>} Array of symbol objects
 */
export const searchSymbols = async (query, exchange = null) => {
    try {
        logger.debug('[MarketData] Searching symbols:', { query, exchange });

        const params = { query };
        if (exchange) {
            params.exchange = exchange;
        }

        const data = await callBackendAPI('/search', params);
        return data || [];
    } catch (error) {
        logger.error('[MarketData] Search error:', error.message);
        return [];
    }
};

/**
 * Clear historical data cache
 * @param {string} symbol - Optional: clear only for this symbol
 */
export const clearHistoricalCache = (symbol = null) => {
    if (symbol) {
        // Clear all entries for this symbol
        for (const key of historicalDataCache.keys()) {
            if (key.startsWith(symbol + ':')) {
                historicalDataCache.delete(key);
            }
        }
        logger.debug('[MarketData] Cache cleared for symbol:', symbol);
    } else {
        historicalDataCache.clear();
        logger.debug('[MarketData] Full cache cleared');
    }
};

/**
 * Get cache statistics
 * @returns {Object} Cache stats
 */
export const getCacheStats = () => {
    return {
        size: historicalDataCache.size,
        entries: Array.from(historicalDataCache.keys())
    };
};

export default {
    getHistoricalData,
    getQuote,
    getBatchQuotes,
    searchSymbols,
    clearHistoricalCache,
    getCacheStats
};
