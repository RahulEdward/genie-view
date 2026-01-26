import { useState, useEffect, useRef } from 'react';
import {
    getPositionBook,
    getOrderBook,
    getFunds,
    getHoldings,
    getTradeBook
} from '../services/angelalgo';
import { eventService, Events } from '../services/eventService';
import logger from '../utils/logger';

export const useTradingData = (isAuthenticated) => {
    const [positions, setPositions] = useState([]);
    const [orders, setOrders] = useState([]);
    const [funds, setFunds] = useState({});
    const [holdings, setHoldings] = useState([]);
    const [trades, setTrades] = useState([]);
    const [activeOrders, setActiveOrders] = useState([]);
    const [activePositions, setActivePositions] = useState([]);

    // Use refs to track if component is mounted to prevent state updates after unmount
    const isMounted = useRef(true);
    // Track if a fetch is already in progress to prevent duplicate calls
    const isFetching = useRef(false);
    // Track last fetch time to prevent rapid successive calls
    const lastFetchTime = useRef(0);

    useEffect(() => {
        isMounted.current = true;
        return () => {
            isMounted.current = false;
        };
    }, []);

    // Event-driven data refresh
    useEffect(() => {
        if (!isAuthenticated) return;

        // Subscribe to events that require data refresh
        const unsubscribers = [
            // Order events - refresh orders and funds
            eventService.on(Events.ORDER_PLACED, () => {
                logger.debug('[useTradingData] Order placed - refreshing orders and funds');
                refreshOrders();
                refreshFunds();
            }),
            eventService.on(Events.ORDER_MODIFIED, () => {
                logger.debug('[useTradingData] Order modified - refreshing orders');
                refreshOrders();
            }),
            eventService.on(Events.ORDER_CANCELLED, () => {
                logger.debug('[useTradingData] Order cancelled - refreshing orders and funds');
                refreshOrders();
                refreshFunds();
            }),

            // Position events - refresh positions, funds, and trades
            eventService.on(Events.POSITION_CLOSED, () => {
                logger.debug('[useTradingData] Position closed - refreshing positions, funds, and trades');
                refreshPositions();
                refreshFunds();
                refreshTrades();
            }),
            eventService.on(Events.POSITION_UPDATED, () => {
                logger.debug('[useTradingData] Position updated - refreshing positions');
                refreshPositions();
            }),

            // Trade events - refresh trades and positions
            eventService.on(Events.TRADE_EXECUTED, () => {
                logger.debug('[useTradingData] Trade executed - refreshing trades and positions');
                refreshTrades();
                refreshPositions();
            }),

            // Funds events - refresh funds
            eventService.on(Events.FUNDS_UPDATED, () => {
                logger.debug('[useTradingData] Funds updated - refreshing funds');
                refreshFunds();
            }),

            // Generic refresh event - refresh all data
            eventService.on(Events.DATA_REFRESH, () => {
                logger.debug('[useTradingData] Data refresh requested - refreshing all data');
                refreshTradingData();
            })
        ];

        // Cleanup subscriptions on unmount
        return () => {
            unsubscribers.forEach(unsubscribe => unsubscribe());
        };
    }, [isAuthenticated]);

    // Individual refresh functions for targeted updates
    const refreshOrders = async () => {
        if (!isMounted.current) return;
        try {
            const orderData = await getOrderBook();
            const orderList = Array.isArray(orderData.orders) ? orderData.orders : [];
            setOrders(orderList);

            const active = orderList.filter(o => {
                const status = (o.status || o.order_status || '').toUpperCase().replace(/\s+/g, '_');
                return ['OPEN', 'PENDING', 'TRIGGER_PENDING', 'VALIDATION_PENDING'].includes(status);
            });
            setActiveOrders(active);
        } catch (error) {
            logger.error('[useTradingData] Error refreshing orders:', error);
        }
    };

    const refreshPositions = async () => {
        if (!isMounted.current) return;
        try {
            const posData = await getPositionBook();
            const positionsList = Array.isArray(posData) ? posData : [];
            setPositions(positionsList);

            const activePos = positionsList.filter(p => parseFloat(p.quantity || 0) !== 0);
            setActivePositions(activePos);
        } catch (error) {
            logger.error('[useTradingData] Error refreshing positions:', error);
        }
    };

    const refreshFunds = async () => {
        if (!isMounted.current) return;
        try {
            const fundsData = await getFunds();
            setFunds(fundsData || {});
        } catch (error) {
            logger.error('[useTradingData] Error refreshing funds:', error);
        }
    };

    const refreshTrades = async () => {
        if (!isMounted.current) return;
        try {
            const tradeData = await getTradeBook();
            const tradeList = Array.isArray(tradeData) ? tradeData : [];
            setTrades(tradeList);
        } catch (error) {
            logger.error('[useTradingData] Error refreshing trades:', error);
        }
    };

    useEffect(() => {
        let intervalId;

        // Helper to add delay between API calls to avoid rate limiting
        const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

        const fetchData = async () => {
            // Check if authenticated AND API key exists
            const apiKey = localStorage.getItem('aa_apikey');
            if (!isAuthenticated || !apiKey) return;

            // Prevent duplicate fetches - if already fetching, skip
            if (isFetching.current) {
                logger.debug('[useTradingData] Fetch already in progress, skipping');
                return;
            }

            // Prevent rapid successive calls - minimum 5 seconds between fetches
            const now = Date.now();
            if (now - lastFetchTime.current < 5000) {
                logger.debug('[useTradingData] Too soon since last fetch, skipping');
                return;
            }

            isFetching.current = true;
            lastFetchTime.current = now;

            try {
                // Fetch data sequentially with delays to avoid Angel One rate limits
                // Angel One has ~25-30 requests/minute limit (~2 requests per second max)
                // Using 500ms delay between calls to stay well under the limit
                const posData = await getPositionBook();
                await delay(500);
                
                const orderData = await getOrderBook();
                await delay(500);
                
                const fundsData = await getFunds();
                await delay(500);
                
                const holdingsData = await getHoldings();
                await delay(500);
                
                const tradeData = await getTradeBook();

                if (!isMounted.current) return;

                // Positions
                // getPositionBook returns array directly in service implementation or []
                const positionsList = Array.isArray(posData) ? posData : [];
                setPositions(positionsList);

                if (positionsList.length > 0) {
                    console.log('[useTradingData] Positions:', positionsList);
                }

                // Orders
                // getOrderBook returns { orders: [], statistics: {} }
                const orderList = Array.isArray(orderData.orders) ? orderData.orders : [];
                setOrders(orderList);

                // Funds
                setFunds(fundsData || {});

                // Holdings
                const holdingsList = holdingsData && Array.isArray(holdingsData.holdings) ? holdingsData.holdings : [];
                setHoldings(holdingsList);

                // Trades
                const tradeList = Array.isArray(tradeData) ? tradeData : [];
                setTrades(tradeList);

                // Filter Active Orders for Chart
                // Status: OPEN, TRIGGER PENDING (with normalization), VALIDATION PENDING
                const active = orderList.filter(o => {
                    // Check both status and order_status fields for compatibility
                    const status = (o.status || o.order_status || '').toUpperCase().replace(/\s+/g, '_'); // Normalize "Trigger Pending" -> "TRIGGER_PENDING"
                    return ['OPEN', 'PENDING', 'TRIGGER_PENDING', 'VALIDATION_PENDING'].includes(status);
                });
                setActiveOrders(active);

                // Active Positions for Chart (non-closed)
                // Assuming all positions in book are open unless quantity is 0
                // Some brokers remove closed positions from the book immediately
                const activePos = positionsList.filter(p => parseFloat(p.quantity || 0) !== 0);
                setActivePositions(activePos);

            } catch (error) {
                console.error("Error fetching trading data:", error);
            } finally {
                isFetching.current = false;
            }
        };

        // Initial fetch
        fetchData();

        // Poll every 60 seconds to avoid Angel One API rate limits
        intervalId = setInterval(fetchData, 60000);

        return () => clearInterval(intervalId);
    }, [isAuthenticated]);

    // Function to manually refresh data (e.g. after placing an order)
    const refreshTradingData = async () => {
        // Check if authenticated AND API key exists
        const apiKey = localStorage.getItem('aa_apikey');
        if (!isAuthenticated || !apiKey) return;

        // Prevent duplicate fetches
        if (isFetching.current) {
            logger.debug('[useTradingData] Manual refresh skipped - fetch in progress');
            return;
        }

        // Prevent rapid successive calls - minimum 3 seconds between manual refreshes
        const now = Date.now();
        if (now - lastFetchTime.current < 3000) {
            logger.debug('[useTradingData] Manual refresh skipped - too soon');
            return;
        }

        isFetching.current = true;
        lastFetchTime.current = now;

        // Helper to add delay between API calls
        const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

        try {
            // Fetch data sequentially with delays to avoid rate limits
            // Using 500ms delay between calls to stay well under Angel One's limit
            const posData = await getPositionBook();
            await delay(500);
            
            const orderData = await getOrderBook();
            await delay(500);
            
            const fundsData = await getFunds();
            await delay(500);
            
            const holdingsData = await getHoldings();
            await delay(500);
            
            const tradeData = await getTradeBook();

            if (!isMounted.current) return;

            const positionsList = Array.isArray(posData) ? posData : [];
            setPositions(positionsList);

            const orderList = Array.isArray(orderData.orders) ? orderData.orders : [];
            setOrders(orderList);

            setFunds(fundsData || {});

            setHoldings(holdingsData && Array.isArray(holdingsData.holdings) ? holdingsData.holdings : []);

            setTrades(Array.isArray(tradeData) ? tradeData : []);

            const active = orderList.filter(o => {
                const status = (o.status || '').toUpperCase().replace(/\s+/g, '_');
                return ['OPEN', 'PENDING', 'TRIGGER_PENDING', 'VALIDATION_PENDING'].includes(status);
            });
            setActiveOrders(active);

            const activePos = positionsList.filter(p => parseFloat(p.quantity || 0) !== 0);
            setActivePositions(activePos);

        } catch (error) {
            console.error("Error refreshing trading data:", error);
        } finally {
            isFetching.current = false;
        }
    };

    return {
        positions,
        orders,
        funds,
        holdings,
        trades,
        activeOrders,
        activePositions,
        refreshTradingData
    };
};
