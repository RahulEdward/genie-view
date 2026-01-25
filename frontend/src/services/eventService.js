/**
 * Event Service
 * Centralized event emitter for data synchronization across components
 * 
 * Events:
 * - order:placed - When a new order is placed
 * - order:modified - When an order is modified
 * - order:cancelled - When an order is cancelled
 * - position:opened - When a new position is opened
 * - position:closed - When a position is closed
 * - position:updated - When position data changes
 * - funds:updated - When account funds change
 * - trade:executed - When a trade is executed
 * - data:refresh - Generic refresh event
 */

import logger from '../utils/logger';

class EventService {
    constructor() {
        this.listeners = new Map(); // Map<eventName, Set<callback>>
    }

    /**
     * Subscribe to an event
     * @param {string} eventName - Event name
     * @param {Function} callback - Callback function
     * @returns {Function} Unsubscribe function
     */
    on(eventName, callback) {
        if (!this.listeners.has(eventName)) {
            this.listeners.set(eventName, new Set());
        }

        this.listeners.get(eventName).add(callback);
        logger.debug('[Events] Subscribed to:', eventName);

        // Return unsubscribe function
        return () => this.off(eventName, callback);
    }

    /**
     * Unsubscribe from an event
     * @param {string} eventName - Event name
     * @param {Function} callback - Callback function to remove
     */
    off(eventName, callback) {
        const callbacks = this.listeners.get(eventName);
        if (callbacks) {
            callbacks.delete(callback);
            logger.debug('[Events] Unsubscribed from:', eventName);

            // Clean up empty sets
            if (callbacks.size === 0) {
                this.listeners.delete(eventName);
            }
        }
    }

    /**
     * Emit an event
     * @param {string} eventName - Event name
     * @param {any} data - Event data
     */
    emit(eventName, data = null) {
        const callbacks = this.listeners.get(eventName);
        
        if (callbacks && callbacks.size > 0) {
            logger.debug('[Events] Emitting:', eventName, data);
            
            callbacks.forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    logger.error('[Events] Callback error:', { eventName, error: error.message });
                }
            });
        }
    }

    /**
     * Subscribe to an event once (auto-unsubscribe after first call)
     * @param {string} eventName - Event name
     * @param {Function} callback - Callback function
     * @returns {Function} Unsubscribe function
     */
    once(eventName, callback) {
        const wrappedCallback = (data) => {
            callback(data);
            this.off(eventName, wrappedCallback);
        };

        return this.on(eventName, wrappedCallback);
    }

    /**
     * Clear all listeners for an event
     * @param {string} eventName - Event name (optional, clears all if not provided)
     */
    clear(eventName = null) {
        if (eventName) {
            this.listeners.delete(eventName);
            logger.debug('[Events] Cleared listeners for:', eventName);
        } else {
            this.listeners.clear();
            logger.debug('[Events] Cleared all listeners');
        }
    }

    /**
     * Get listener count for an event
     * @param {string} eventName - Event name
     * @returns {number} Number of listeners
     */
    listenerCount(eventName) {
        const callbacks = this.listeners.get(eventName);
        return callbacks ? callbacks.size : 0;
    }
}

// Singleton instance
export const eventService = new EventService();

// Event name constants for type safety
export const Events = {
    // Order events
    ORDER_PLACED: 'order:placed',
    ORDER_MODIFIED: 'order:modified',
    ORDER_CANCELLED: 'order:cancelled',
    
    // Position events
    POSITION_OPENED: 'position:opened',
    POSITION_CLOSED: 'position:closed',
    POSITION_UPDATED: 'position:updated',
    
    // Account events
    FUNDS_UPDATED: 'funds:updated',
    
    // Trade events
    TRADE_EXECUTED: 'trade:executed',
    
    // Generic refresh
    DATA_REFRESH: 'data:refresh'
};

export default eventService;
