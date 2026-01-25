/**
 * WebSocket Manager - Wrapper around angelalgo's sharedWebSocket
 * Provides a consistent API for WebSocket management across the app
 * Updated: 2026-01-19 17:00
 */

import { sharedWebSocket } from './angelalgo.js';

// WebSocket connection states
const WS_STATES = {
  DISCONNECTED: 'DISCONNECTED',
  CONNECTING: 'CONNECTING',
  CONNECTED: 'CONNECTED',
  AUTHENTICATED: 'AUTHENTICATED',
  RECONNECTING: 'RECONNECTING',
  ERROR: 'ERROR'
};

class WebSocketManager {
  constructor() {
    this.subscriptions = new Map(); // symbol:exchange -> unsubscribe function
    this.stateListeners = new Set();
    this.state = WS_STATES.DISCONNECTED;
  }

  /**
   * Connect to WebSocket server
   * Uses angelalgo's sharedWebSocket which auto-connects
   */
  connect() {
    // angelalgo's sharedWebSocket connects automatically when subscribing
    // Just update state
    this.setState(WS_STATES.CONNECTED);
    console.log('[WebSocketManager] Connected via angelalgo');
  }

  /**
   * Subscribe to symbol updates
   * @param {string} symbol - Trading symbol
   * @param {string} exchange - Exchange code
   * @param {function} callback - Callback function for updates
   */
  subscribe(symbol, exchange, callback) {
    const key = `${symbol}:${exchange}`;
    
    // Use angelalgo's sharedWebSocket
    const unsubscribe = sharedWebSocket.subscribe(
      [{ symbol, exchange }],
      (data) => {
        // Transform data to match expected format
        if (data.type === 'market_data' && data.symbol === symbol) {
          callback(data.data || data);
        }
      },
      2 // mode 2 for LTP updates
    );

    // Store unsubscribe function
    this.subscriptions.set(key, unsubscribe);
    
    console.log(`[WebSocketManager] Subscribed to ${key}`);
  }

  /**
   * Unsubscribe from symbol updates
   * @param {string} symbol - Trading symbol
   * @param {string} exchange - Exchange code
   */
  unsubscribe(symbol, exchange) {
    const key = `${symbol}:${exchange}`;
    const unsubscribe = this.subscriptions.get(key);
    
    if (unsubscribe && typeof unsubscribe.close === 'function') {
      unsubscribe.close();
      this.subscriptions.delete(key);
      console.log(`[WebSocketManager] Unsubscribed from ${key}`);
    }
  }

  /**
   * Disconnect WebSocket
   */
  disconnect() {
    // Unsubscribe from all
    this.subscriptions.forEach((unsubscribe, key) => {
      if (unsubscribe && typeof unsubscribe.close === 'function') {
        unsubscribe.close();
      }
    });
    this.subscriptions.clear();
    this.setState(WS_STATES.DISCONNECTED);
    console.log('[WebSocketManager] Disconnected');
  }

  setState(newState) {
    if (this.state === newState) return;
    const oldState = this.state;
    this.state = newState;
    console.log(`[WebSocketManager] State: ${oldState} -> ${newState}`);
    this.stateListeners.forEach(listener => {
      try {
        listener(newState, oldState);
      } catch (error) {
        console.error('[WebSocketManager] State listener error:', error);
      }
    });
  }

  onStateChange(listener) {
    this.stateListeners.add(listener);
    return () => this.stateListeners.delete(listener);
  }

  getState() {
    return this.state;
  }

  isConnected() {
    return this.state === WS_STATES.CONNECTED || this.state === WS_STATES.AUTHENTICATED;
  }
}

const wsManager = new WebSocketManager();

export { wsManager, WS_STATES };
