# Design Document: Frontend-Backend Integration

## Overview

Yeh document frontend trading dashboard aur AngelOne backend ke beech complete integration ka technical design describe karta hai. Design ka focus hai existing functionality ko maintain karte hue sabhi features ko properly connect karna. Architecture event-driven hai with WebSocket for real-time updates aur REST APIs for data fetching.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (React Dashboard)                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Components: Chart, Watchlist, OptionChain, AccountPanel │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │         Service Layer (API Integration)                   │   │
│  │  accountService, marketService, optionChain, angelalgo   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │         WebSocket Manager (Real-time Updates)            │   │
│  │         SharedWebSocketManager                            │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  REST APIs: /auth, /funds, /positions, /orders, /quotes │   │
│  │  /history, /optionchain, /greeks, /search, /market      │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  WebSocket: /ws (Real-time market data streaming)       │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     AngelOne Broker APIs                         │
│  REST APIs + WebSocket Feed                                      │
└─────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Service Layer Refactoring


#### Current State Analysis

Frontend currently has multiple service files:
- `apiConfig.js` - API configuration and URL management
- `accountService.js` - Account operations (funds, positions, orders)
- `marketService.js` - Market timings and holidays
- `optionChain.js` - Option chain data
- `angelalgo.js` - Direct AngelOne API calls (needs to be replaced with backend calls)

#### Design Changes

**Replace Direct Broker Calls with Backend Calls:**
```javascript
// OLD: Direct AngelOne API calls in angelalgo.js
const response = await fetch('https://apiconnect.angelone.in/...');

// NEW: Backend API calls
const response = await fetch(`${getApiBase()}/endpoint`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ apikey: getApiKey(), ...params })
});
```

**Unified API Service Pattern:**
```javascript
// services/apiService.js
export const callBackendAPI = async (endpoint, params = {}) => {
    const apiKey = getApiKey();
    if (!apiKey) throw new Error('Not authenticated');
    
    const response = await fetch(`${getApiBase()}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ apikey: apiKey, ...params })
    });
    
    if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
    }
    
    const data = await response.json();
    if (data.status !== 'success') {
        throw new Error(data.message || 'API call failed');
    }
    
    return data.data;
};
```

### 2. WebSocket Integration


#### WebSocket Manager Design

```javascript
// services/websocketManager.js
class WebSocketManager {
    constructor() {
        this.ws = null;
        this.subscriptions = new Map(); // symbol -> Set of callbacks
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.heartbeatInterval = null;
        this.isAuthenticated = false;
    }
    
    connect() {
        const wsUrl = getWebSocketUrl();
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('[WS] Connected');
            this.authenticate();
            this.reconnectAttempts = 0;
            this.startHeartbeat();
        };
        
        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
        };
        
        this.ws.onclose = () => {
            console.log('[WS] Disconnected');
            this.stopHeartbeat();
            this.handleReconnect();
        };
        
        this.ws.onerror = (error) => {
            console.error('[WS] Error:', error);
        };
    }
    
    authenticate() {
        const apiKey = getApiKey();
        this.send({
            action: 'authenticate',
            api_key: apiKey
        });
    }
    
    subscribe(symbol, exchange, callback, mode = 2) {
        const key = `${symbol}:${exchange}`;
        
        if (!this.subscriptions.has(key)) {
            this.subscriptions.set(key, new Set());
            
            // Send subscribe message to backend
            this.send({
                action: 'subscribe',
                symbol,
                exchange,
                mode
            });
        }
        
        this.subscriptions.get(key).add(callback);
    }
    
    unsubscribe(symbol, exchange, callback) {
        const key = `${symbol}:${exchange}`;
        const callbacks = this.subscriptions.get(key);
        
        if (callbacks) {
            callbacks.delete(callback);
            
            if (callbacks.size === 0) {
                this.subscriptions.delete(key);
                
                // Send unsubscribe message to backend
                this.send({
                    action: 'unsubscribe',
                    symbol,
                    exchange
                });
            }
        }
    }
    
    handleMessage(message) {
        if (message.type === 'auth') {
            this.isAuthenticated = message.status === 'success';
            console.log('[WS] Authentication:', message.status);
            
            if (this.isAuthenticated) {
                // Resubscribe to all symbols after reconnect
                this.resubscribeAll();
            }
        } else if (message.type === 'market_data') {
            const key = `${message.symbol}:${message.exchange}`;
            const callbacks = this.subscriptions.get(key);
            
            if (callbacks) {
                callbacks.forEach(callback => callback(message.data));
            }
        } else if (message.type === 'ping') {
            this.send({ type: 'pong' });
        }
    }
    
    resubscribeAll() {
        this.subscriptions.forEach((callbacks, key) => {
            const [symbol, exchange] = key.split(':');
            this.send({
                action: 'subscribe',
                symbol,
                exchange,
                mode: 2
            });
        });
    }
    
    startHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            if (this.ws?.readyState === WebSocket.OPEN) {
                this.send({ type: 'ping' });
            }
        }, 30000); // 30 seconds
    }
    
    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }
    
    handleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
            
            console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
            
            setTimeout(() => {
                this.connect();
            }, delay);
        } else {
            console.error('[WS] Max reconnect attempts reached');
        }
    }
    
    send(data) {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }
    
    disconnect() {
        this.stopHeartbeat();
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.subscriptions.clear();
    }
}

// Singleton instance
export const wsManager = new WebSocketManager();
```

### 3. Account Service Integration


#### Account Service Updates

```javascript
// services/accountService.js - Updated implementation

/**
 * Get Funds - Fetch account balance and margin details
 */
export const getFunds = async () => {
    try {
        return await callBackendAPI('/funds');
    } catch (error) {
        console.error('[AccountService] Funds error:', error);
        return null;
    }
};

/**
 * Get Position Book - Fetch current open positions
 */
export const getPositionBook = async () => {
    try {
        return await callBackendAPI('/positionbook') || [];
    } catch (error) {
        console.error('[AccountService] PositionBook error:', error);
        return [];
    }
};

/**
 * Get Order Book - Fetch all orders with statistics
 */
export const getOrderBook = async () => {
    try {
        return await callBackendAPI('/orderbook') || { orders: [], statistics: {} };
    } catch (error) {
        console.error('[AccountService] OrderBook error:', error);
        return { orders: [], statistics: {} };
    }
};

/**
 * Get Trade Book - Fetch executed trades
 */
export const getTradeBook = async () => {
    try {
        return await callBackendAPI('/tradebook') || [];
    } catch (error) {
        console.error('[AccountService] TradeBook error:', error);
        return [];
    }
};

/**
 * Get Holdings - Fetch long-term stock holdings with P&L
 */
export const getHoldings = async () => {
    try {
        return await callBackendAPI('/holdings') || { holdings: [], statistics: {} };
    } catch (error) {
        console.error('[AccountService] Holdings error:', error);
        return { holdings: [], statistics: {} };
    }
};

/**
 * Place Order - Submit new order
 */
export const placeOrder = async (orderParams) => {
    try {
        return await callBackendAPI('/placeorder', orderParams);
    } catch (error) {
        console.error('[AccountService] PlaceOrder error:', error);
        throw error;
    }
};

/**
 * Modify Order - Update existing order
 */
export const modifyOrder = async (orderParams) => {
    try {
        return await callBackendAPI('/modifyorder', orderParams);
    } catch (error) {
        console.error('[AccountService] ModifyOrder error:', error);
        throw error;
    }
};

/**
 * Cancel Order - Cancel pending order
 */
export const cancelOrder = async (orderId) => {
    try {
        return await callBackendAPI('/cancelorder', { orderid: orderId });
    } catch (error) {
        console.error('[AccountService] CancelOrder error:', error);
        throw error;
    }
};

/**
 * Close Position - Exit position
 */
export const closePosition = async (positionParams) => {
    try {
        return await callBackendAPI('/closeposition', positionParams);
    } catch (error) {
        console.error('[AccountService] ClosePosition error:', error);
        throw error;
    }
};
```

### 4. Market Data Service Integration


#### Market Data Service Updates

```javascript
// services/marketDataService.js - New service for market data

/**
 * Get Historical OHLC Data
 */
export const getHistoricalData = async (symbol, exchange, interval, startDate, endDate) => {
    try {
        return await callBackendAPI('/history', {
            symbol,
            exchange,
            interval,
            start_date: startDate,
            end_date: endDate
        });
    } catch (error) {
        console.error('[MarketData] Historical data error:', error);
        return [];
    }
};

/**
 * Get Current Quote
 */
export const getQuote = async (symbol, exchange) => {
    try {
        return await callBackendAPI('/quotes', { symbol, exchange });
    } catch (error) {
        console.error('[MarketData] Quote error:', error);
        return null;
    }
};

/**
 * Get Batch Quotes
 */
export const getBatchQuotes = async (symbols) => {
    try {
        return await callBackendAPI('/quotes/batch', { symbols });
    } catch (error) {
        console.error('[MarketData] Batch quotes error:', error);
        return [];
    }
};

/**
 * Search Symbols
 */
export const searchSymbols = async (query, exchange = null) => {
    try {
        return await callBackendAPI('/search', { query, exchange });
    } catch (error) {
        console.error('[MarketData] Search error:', error);
        return [];
    }
};
```

### 5. Option Chain Service Integration


#### Option Chain Service Updates

```javascript
// services/optionChainService.js - Updated implementation

/**
 * Get Option Chain
 */
export const getOptionChain = async (underlying, exchange = 'NFO', expiryDate = null, strikeCount = 15) => {
    try {
        const cacheKey = `${underlying}_${exchange}_${expiryDate}`;
        
        // Check cache first
        const cached = optionChainCache.get(cacheKey);
        if (cached && isCacheValid(cached)) {
            return cached.data;
        }
        
        // Fetch from backend
        const data = await callBackendAPI('/optionchain', {
            underlying,
            exchange,
            expiry: expiryDate,
            strike_count: strikeCount
        });
        
        // Cache the result
        optionChainCache.set(cacheKey, {
            data,
            timestamp: Date.now()
        });
        
        return data;
    } catch (error) {
        console.error('[OptionChain] Error:', error);
        
        // Return cached data if available
        const cached = optionChainCache.get(`${underlying}_${exchange}_${expiryDate}`);
        if (cached) {
            return cached.data;
        }
        
        return {
            underlying,
            exchange,
            underlyingLTP: 0,
            atmStrike: 0,
            expiryDate: null,
            chain: []
        };
    }
};

/**
 * Get Available Expiries
 */
export const getAvailableExpiries = async (underlying, exchange = 'NFO', instrumenttype = 'options') => {
    try {
        return await callBackendAPI('/expiry', {
            underlying,
            exchange,
            instrumenttype
        });
    } catch (error) {
        console.error('[OptionChain] Expiry error:', error);
        return [];
    }
};

/**
 * Get Option Greeks
 */
export const getOptionGreeks = async (symbol, exchange = 'NFO') => {
    try {
        return await callBackendAPI('/greeks', { symbol, exchange });
    } catch (error) {
        console.error('[OptionChain] Greeks error:', error);
        return null;
    }
};

/**
 * Get Batch Option Greeks
 */
export const getBatchOptionGreeks = async (symbols) => {
    try {
        return await callBackendAPI('/greeks/batch', { symbols });
    } catch (error) {
        console.error('[OptionChain] Batch Greeks error:', error);
        return [];
    }
};
```

### 6. Chart Integration


#### Chart Component Updates

```javascript
// components/Chart/ChartComponent.jsx - Integration updates

const ChartComponent = ({ symbol, exchange, interval }) => {
    const [chartData, setChartData] = useState([]);
    const [loading, setLoading] = useState(true);
    const chartRef = useRef(null);
    
    // Fetch historical data on mount and interval change
    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            try {
                const endDate = new Date();
                const startDate = new Date();
                startDate.setDate(startDate.getDate() - 30); // Last 30 days
                
                const data = await getHistoricalData(
                    symbol,
                    exchange,
                    interval,
                    startDate.toISOString().split('T')[0],
                    endDate.toISOString().split('T')[0]
                );
                
                setChartData(data);
            } catch (error) {
                console.error('Chart data fetch error:', error);
            } finally {
                setLoading(false);
            }
        };
        
        fetchData();
    }, [symbol, exchange, interval]);
    
    // Subscribe to live updates via WebSocket
    useEffect(() => {
        const handleTick = (tick) => {
            // Update chart with live tick
            updateChartWithTick(tick);
        };
        
        wsManager.subscribe(symbol, exchange, handleTick);
        
        return () => {
            wsManager.unsubscribe(symbol, exchange, handleTick);
        };
    }, [symbol, exchange]);
    
    const updateChartWithTick = (tick) => {
        // Update last candle or create new candle based on tick
        setChartData(prevData => {
            const newData = [...prevData];
            const lastCandle = newData[newData.length - 1];
            
            if (lastCandle && isInSameInterval(lastCandle.timestamp, tick.timestamp, interval)) {
                // Update existing candle
                lastCandle.high = Math.max(lastCandle.high, tick.ltp);
                lastCandle.low = Math.min(lastCandle.low, tick.ltp);
                lastCandle.close = tick.ltp;
                lastCandle.volume += tick.volume || 0;
            } else {
                // Create new candle
                newData.push({
                    timestamp: tick.timestamp,
                    open: tick.ltp,
                    high: tick.ltp,
                    low: tick.ltp,
                    close: tick.ltp,
                    volume: tick.volume || 0
                });
            }
            
            return newData;
        });
    };
    
    return (
        <div className="chart-container">
            {loading ? (
                <div className="loading">Loading chart data...</div>
            ) : (
                <TradingViewChart
                    ref={chartRef}
                    data={chartData}
                    symbol={symbol}
                    interval={interval}
                />
            )}
        </div>
    );
};
```

### 7. Watchlist Integration


#### Watchlist Component Updates

```javascript
// components/Watchlist/Watchlist.jsx - Integration updates

const Watchlist = () => {
    const [symbols, setSymbols] = useState([]);
    const [quotes, setQuotes] = useState({});
    
    // Subscribe to live updates for all symbols
    useEffect(() => {
        const callbacks = new Map();
        
        symbols.forEach(({ symbol, exchange }) => {
            const callback = (tick) => {
                setQuotes(prev => ({
                    ...prev,
                    [`${symbol}:${exchange}`]: {
                        ltp: tick.ltp,
                        change: tick.change,
                        changePercent: tick.change_percent,
                        volume: tick.volume
                    }
                }));
            };
            
            callbacks.set(`${symbol}:${exchange}`, callback);
            wsManager.subscribe(symbol, exchange, callback);
        });
        
        return () => {
            callbacks.forEach((callback, key) => {
                const [symbol, exchange] = key.split(':');
                wsManager.unsubscribe(symbol, exchange, callback);
            });
        };
    }, [symbols]);
    
    const addSymbol = async (symbol, exchange) => {
        // Fetch initial quote
        const quote = await getQuote(symbol, exchange);
        
        setSymbols(prev => [...prev, { symbol, exchange }]);
        setQuotes(prev => ({
            ...prev,
            [`${symbol}:${exchange}`]: quote
        }));
    };
    
    const removeSymbol = (symbol, exchange) => {
        setSymbols(prev => prev.filter(s => 
            !(s.symbol === symbol && s.exchange === exchange)
        ));
        
        setQuotes(prev => {
            const newQuotes = { ...prev };
            delete newQuotes[`${symbol}:${exchange}`];
            return newQuotes;
        });
    };
    
    return (
        <div className="watchlist">
            {symbols.map(({ symbol, exchange }) => {
                const quote = quotes[`${symbol}:${exchange}`];
                return (
                    <WatchlistItem
                        key={`${symbol}:${exchange}`}
                        symbol={symbol}
                        exchange={exchange}
                        quote={quote}
                        onRemove={() => removeSymbol(symbol, exchange)}
                    />
                );
            })}
        </div>
    );
};
```

### 8. Account Panel Integration


#### Account Panel Component Updates

```javascript
// components/AccountPanel/AccountPanel.jsx - Integration updates

const AccountPanel = () => {
    const [activeTab, setActiveTab] = useState('positions');
    const [funds, setFunds] = useState(null);
    const [positions, setPositions] = useState([]);
    const [orders, setOrders] = useState({ orders: [], statistics: {} });
    const [trades, setTrades] = useState([]);
    const [holdings, setHoldings] = useState({ holdings: [], statistics: {} });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    
    // Auto-refresh data every 5 seconds
    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            setError(null);
            
            try {
                switch (activeTab) {
                    case 'funds':
                        const fundsData = await getFunds();
                        setFunds(fundsData);
                        break;
                    case 'positions':
                        const positionsData = await getPositionBook();
                        setPositions(positionsData);
                        break;
                    case 'orders':
                        const ordersData = await getOrderBook();
                        setOrders(ordersData);
                        break;
                    case 'trades':
                        const tradesData = await getTradeBook();
                        setTrades(tradesData);
                        break;
                    case 'holdings':
                        const holdingsData = await getHoldings();
                        setHoldings(holdingsData);
                        break;
                }
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };
        
        fetchData();
        const interval = setInterval(fetchData, 5000); // Refresh every 5 seconds
        
        return () => clearInterval(interval);
    }, [activeTab]);
    
    // Subscribe to live position updates
    useEffect(() => {
        if (activeTab === 'positions' && positions.length > 0) {
            const callbacks = new Map();
            
            positions.forEach(position => {
                const callback = (tick) => {
                    // Update position P&L with live price
                    setPositions(prev => prev.map(p => {
                        if (p.symbol === position.symbol && p.exchange === position.exchange) {
                            const ltp = tick.ltp;
                            const pnl = (ltp - p.averagePrice) * p.quantity;
                            return { ...p, ltp, pnl };
                        }
                        return p;
                    }));
                };
                
                callbacks.set(`${position.symbol}:${position.exchange}`, callback);
                wsManager.subscribe(position.symbol, position.exchange, callback);
            });
            
            return () => {
                callbacks.forEach((callback, key) => {
                    const [symbol, exchange] = key.split(':');
                    wsManager.unsubscribe(symbol, exchange, callback);
                });
            };
        }
    }, [activeTab, positions]);
    
    const handleExitPosition = async (position) => {
        try {
            await closePosition({
                symbol: position.symbol,
                exchange: position.exchange,
                quantity: position.quantity,
                product: position.product
            });
            
            // Refresh positions
            const positionsData = await getPositionBook();
            setPositions(positionsData);
            
            toast.success('Position closed successfully');
        } catch (error) {
            toast.error(`Failed to close position: ${error.message}`);
        }
    };
    
    const handleCancelOrder = async (orderId) => {
        try {
            await cancelOrder(orderId);
            
            // Refresh orders
            const ordersData = await getOrderBook();
            setOrders(ordersData);
            
            toast.success('Order cancelled successfully');
        } catch (error) {
            toast.error(`Failed to cancel order: ${error.message}`);
        }
    };
    
    return (
        <div className="account-panel">
            <div className="tabs">
                <button onClick={() => setActiveTab('funds')}>Funds</button>
                <button onClick={() => setActiveTab('positions')}>Positions</button>
                <button onClick={() => setActiveTab('orders')}>Orders</button>
                <button onClick={() => setActiveTab('trades')}>Trades</button>
                <button onClick={() => setActiveTab('holdings')}>Holdings</button>
            </div>
            
            <div className="content">
                {loading && <div className="loading">Loading...</div>}
                {error && <div className="error">{error}</div>}
                
                {activeTab === 'funds' && <FundsView funds={funds} />}
                {activeTab === 'positions' && (
                    <PositionsView 
                        positions={positions} 
                        onExit={handleExitPosition}
                    />
                )}
                {activeTab === 'orders' && (
                    <OrdersView 
                        orders={orders.orders}
                        statistics={orders.statistics}
                        onCancel={handleCancelOrder}
                    />
                )}
                {activeTab === 'trades' && <TradesView trades={trades} />}
                {activeTab === 'holdings' && (
                    <HoldingsView 
                        holdings={holdings.holdings}
                        statistics={holdings.statistics}
                    />
                )}
            </div>
        </div>
    );
};
```

### 9. Authentication Flow


#### Authentication Service

```javascript
// services/authService.js - New authentication service

/**
 * Login to AngelOne via backend
 */
export const login = async (credentials) => {
    try {
        const response = await fetch(`${getApiBase()}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                broker: 'angelone',
                client_id: credentials.clientId,
                password: credentials.password,
                totp: credentials.totp,
                api_key: credentials.apiKey
            })
        });
        
        if (!response.ok) {
            throw new Error(`Login failed: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.status === 'success') {
            // Store API key in localStorage
            localStorage.setItem(STORAGE_KEYS.OA_API_KEY, data.data.apikey);
            
            // Connect WebSocket
            wsManager.connect();
            
            return { success: true, apiKey: data.data.apikey };
        } else {
            throw new Error(data.message || 'Login failed');
        }
    } catch (error) {
        console.error('[Auth] Login error:', error);
        throw error;
    }
};

/**
 * Logout
 */
export const logout = async () => {
    try {
        await callBackendAPI('/auth/logout');
    } catch (error) {
        console.error('[Auth] Logout error:', error);
    } finally {
        // Clear API key
        localStorage.removeItem(STORAGE_KEYS.OA_API_KEY);
        
        // Disconnect WebSocket
        wsManager.disconnect();
    }
};

/**
 * Check if user is authenticated
 */
export const isAuthenticated = () => {
    const apiKey = getApiKey();
    return apiKey && apiKey.trim() !== '';
};

/**
 * Validate API key with backend
 */
export const validateApiKey = async () => {
    try {
        await callBackendAPI('/ping');
        return true;
    } catch (error) {
        return false;
    }
};
```

#### Login Component

```javascript
// components/BrokerLogin/BrokerLogin.jsx - Updated login flow

const BrokerLogin = () => {
    const [credentials, setCredentials] = useState({
        clientId: '',
        password: '',
        totp: '',
        apiKey: ''
    });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    
    const handleLogin = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        
        try {
            const result = await login(credentials);
            
            if (result.success) {
                toast.success('Login successful!');
                // Redirect to dashboard
                window.location.href = '/';
            }
        } catch (err) {
            setError(err.message);
            toast.error(`Login failed: ${err.message}`);
        } finally {
            setLoading(false);
        }
    };
    
    return (
        <div className="broker-login">
            <form onSubmit={handleLogin}>
                <input
                    type="text"
                    placeholder="Client ID"
                    value={credentials.clientId}
                    onChange={(e) => setCredentials({ ...credentials, clientId: e.target.value })}
                    required
                />
                <input
                    type="password"
                    placeholder="Password"
                    value={credentials.password}
                    onChange={(e) => setCredentials({ ...credentials, password: e.target.value })}
                    required
                />
                <input
                    type="text"
                    placeholder="TOTP"
                    value={credentials.totp}
                    onChange={(e) => setCredentials({ ...credentials, totp: e.target.value })}
                    required
                />
                <input
                    type="text"
                    placeholder="API Key"
                    value={credentials.apiKey}
                    onChange={(e) => setCredentials({ ...credentials, apiKey: e.target.value })}
                    required
                />
                
                {error && <div className="error">{error}</div>}
                
                <button type="submit" disabled={loading}>
                    {loading ? 'Logging in...' : 'Login'}
                </button>
            </form>
        </div>
    );
};
```

### 10. Error Handling and Toast Notifications


#### Error Handling Utilities

```javascript
// utils/errorHandler.js - Centralized error handling

/**
 * Handle API errors with user-friendly messages
 */
export const handleApiError = (error, context = '') => {
    console.error(`[${context}] Error:`, error);
    
    let message = 'An error occurred';
    
    if (error.response) {
        // HTTP error response
        const status = error.response.status;
        const data = error.response.data;
        
        if (status === 401) {
            message = 'Authentication failed. Please login again.';
            // Redirect to login
            window.location.href = '/login';
        } else if (status === 429) {
            message = 'Rate limit exceeded. Please try again later.';
        } else if (data?.message) {
            message = data.message;
        } else {
            message = `Error: ${status}`;
        }
    } else if (error.message) {
        message = error.message;
    }
    
    toast.error(message);
    return message;
};

/**
 * Handle WebSocket errors
 */
export const handleWebSocketError = (error) => {
    console.error('[WebSocket] Error:', error);
    toast.error('WebSocket connection error. Retrying...');
};

/**
 * Handle network errors
 */
export const handleNetworkError = (error) => {
    console.error('[Network] Error:', error);
    toast.error('Network error. Please check your connection.');
};
```

#### Toast Notification Service

```javascript
// services/toastService.js - Toast notifications

import { toast as reactToast } from 'react-toastify';

export const toast = {
    success: (message, options = {}) => {
        reactToast.success(message, {
            position: 'top-right',
            autoClose: 3000,
            hideProgressBar: false,
            closeOnClick: true,
            pauseOnHover: true,
            draggable: true,
            ...options
        });
    },
    
    error: (message, options = {}) => {
        reactToast.error(message, {
            position: 'top-right',
            autoClose: 5000,
            hideProgressBar: false,
            closeOnClick: true,
            pauseOnHover: true,
            draggable: true,
            ...options
        });
    },
    
    info: (message, options = {}) => {
        reactToast.info(message, {
            position: 'top-right',
            autoClose: 3000,
            hideProgressBar: false,
            closeOnClick: true,
            pauseOnHover: true,
            draggable: true,
            ...options
        });
    },
    
    warning: (message, options = {}) => {
        reactToast.warning(message, {
            position: 'top-right',
            autoClose: 4000,
            hideProgressBar: false,
            closeOnClick: true,
            pauseOnHover: true,
            draggable: true,
            ...options
        });
    }
};
```

## Data Flow Diagrams

### 1. Authentication Flow

```
User → BrokerLogin Component
         ↓
    authService.login()
         ↓
    POST /api/v1/auth/login
         ↓
    Backend → AngelOne API
         ↓
    JWT Token + API Key
         ↓
    Store in localStorage
         ↓
    Connect WebSocket
         ↓
    Redirect to Dashboard
```

### 2. Live Market Data Flow

```
User adds symbol to Watchlist
         ↓
    wsManager.subscribe(symbol, exchange)
         ↓
    WebSocket: { action: 'subscribe', symbol, exchange }
         ↓
    Backend subscribes to AngelOne WebSocket
         ↓
    AngelOne sends live ticks
         ↓
    Backend forwards to Frontend WebSocket
         ↓
    wsManager receives tick
         ↓
    Calls registered callbacks
         ↓
    Watchlist/Chart updates UI
```

### 3. Historical Chart Data Flow

```
User opens Chart
         ↓
    getHistoricalData(symbol, exchange, interval)
         ↓
    POST /api/v1/history
         ↓
    Backend checks cache
         ↓
    If cache miss → Fetch from AngelOne
         ↓
    Store in database
         ↓
    Return OHLC data
         ↓
    Chart renders candles
         ↓
    Subscribe to live updates via WebSocket
         ↓
    Update last candle with live ticks
```

### 4. Order Placement Flow

```
User fills order form
         ↓
    Validate order parameters
         ↓
    placeOrder(orderParams)
         ↓
    POST /api/v1/placeorder
         ↓
    Backend → AngelOne Order API
         ↓
    Order placed successfully
         ↓
    Return order ID
         ↓
    Show success toast
         ↓
    Refresh order book
         ↓
    Update available margin
```

## Testing Strategy


### Unit Tests

**Service Layer Tests:**
- Test each API service function with mocked fetch
- Test error handling for network failures
- Test caching logic in option chain service
- Test WebSocket manager subscription/unsubscription

**Component Tests:**
- Test Chart component renders with data
- Test Watchlist adds/removes symbols
- Test Account Panel switches tabs correctly
- Test Order form validation

**Integration Tests:**
- Test full authentication flow
- Test WebSocket connection and reconnection
- Test live data updates in components
- Test order placement end-to-end

### Property-Based Tests

Property-based tests will validate universal properties across all inputs:

**Property 1: WebSocket Subscription Consistency**
*For any* symbol and exchange, subscribing then unsubscribing should leave no active subscriptions

**Property 2: Cache Validity**
*For any* cached data, if TTL has not expired, the cache should return the stored data

**Property 3: Data Transformation Integrity**
*For any* API response, transforming to frontend format should preserve all numeric values

**Property 4: Order Parameter Validation**
*For any* order parameters, validation should reject invalid combinations (e.g., negative quantity)

**Property 5: Position P&L Calculation**
*For any* position and live price, P&L should equal (LTP - Average Price) × Quantity

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: WebSocket Subscription Consistency

*For any* symbol and exchange, after subscribing and then unsubscribing, the subscription map should not contain that symbol-exchange pair
**Validates: Requirements 2.5, 10.1**

### Property 2: Cache TTL Expiration

*For any* cached data with TTL, if current time exceeds cache timestamp + TTL, the cache should be considered invalid and fresh data should be fetched
**Validates: Requirements 13.2, 13.4**

### Property 3: API Response Data Integrity

*For any* backend API response containing numeric values (prices, quantities, volumes), transforming to frontend format should preserve all values without loss of precision
**Validates: Requirements 1.1, 2.1, 3.1, 4.1**

### Property 4: Order Validation Completeness

*For any* order parameters, validation should check all required fields (symbol, exchange, quantity, price, order type, product type) and reject if any are missing or invalid
**Validates: Requirements 7.4**

### Property 5: Position P&L Accuracy

*For any* position with average price and quantity, and any live price, the calculated P&L should equal (live price - average price) × quantity × lot size
**Validates: Requirements 1.2, 9.5**

### Property 6: WebSocket Reconnection Idempotence

*For any* WebSocket connection that disconnects and reconnects, all previously subscribed symbols should be automatically resubscribed
**Validates: Requirements 2.4, 10.3, 10.6**

### Property 7: Symbol Search Result Relevance

*For any* search query, all returned results should contain the query string (case-insensitive) in either symbol name or trading symbol
**Validates: Requirements 5.1, 5.3**

### Property 8: Historical Data Completeness

*For any* date range request, the returned OHLC data should cover the entire range without gaps (excluding market holidays and weekends)
**Validates: Requirements 3.1, 3.5**

### Property 9: Option Chain ATM Identification

*For any* option chain with underlying LTP, the ATM strike should be the strike price closest to the underlying LTP
**Validates: Requirements 4.3**

### Property 10: Authentication State Consistency

*For any* user session, if API key exists in localStorage and is valid, all API calls should succeed; if API key is invalid, all API calls should fail with 401 error
**Validates: Requirements 12.3, 12.4**

### Property 11: Live Data Update Frequency

*For any* subscribed symbol, live price updates should be received within 1 second of market tick (under normal network conditions)
**Validates: Requirements 2.1, 2.2**

### Property 12: Order Book Refresh Consistency

*For any* order placement, modification, or cancellation, the order book should be refreshed and reflect the change within 2 seconds
**Validates: Requirements 7.5, 8.4, 8.5**

### Property 13: Error Message User-Friendliness

*For any* API error response, the displayed error message should be human-readable and not contain technical error codes without explanation
**Validates: Requirements 11.2, 11.4**

### Property 14: Cache Size Limit Enforcement

*For any* cache (option chain, historical data), when size exceeds maximum limit, oldest entries should be evicted to maintain size limit
**Validates: Requirements 13.5**

### Property 15: Multi-Symbol Subscription Isolation

*For any* two different symbols subscribed via WebSocket, ticks for symbol A should only trigger callbacks registered for symbol A, not symbol B
**Validates: Requirements 16.1, 16.3**

## Implementation Notes

### Migration Strategy

1. **Phase 1: Service Layer Refactoring**
   - Update all service files to use backend APIs
   - Remove direct AngelOne API calls
   - Add error handling and caching

2. **Phase 2: WebSocket Integration**
   - Implement WebSocketManager
   - Update components to use WebSocket for live data
   - Test reconnection logic

3. **Phase 3: Component Updates**
   - Update Chart component
   - Update Watchlist component
   - Update Account Panel component
   - Update Option Chain component

4. **Phase 4: Authentication Flow**
   - Implement login/logout
   - Add API key validation
   - Add session management

5. **Phase 5: Testing and Bug Fixes**
   - Write unit tests
   - Write integration tests
   - Fix bugs found during testing

### Backward Compatibility

- Keep existing component interfaces unchanged
- Only update internal implementation
- Maintain existing localStorage keys
- Support gradual migration (some features can use old API while others use new)

### Performance Optimizations

- Implement request debouncing for search
- Use batch APIs for multiple symbols
- Cache aggressively with smart invalidation
- Use WebSocket for all real-time data (avoid polling)
- Lazy load components and data

### Error Recovery

- Implement exponential backoff for retries
- Show cached data when API fails
- Provide manual refresh button
- Show connection status indicator
- Log errors for debugging

