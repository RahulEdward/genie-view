/**
 * Account Service
 * Trading account operations - funds, positions, orders, holdings
 * Updated to use unified backend API service
 */

import logger from '../utils/logger.js';
import { callBackendAPI } from './apiService';
import { eventService, Events } from './eventService';

/**
 * Ping API - Check connectivity and validate API key
 * @returns {Promise<Object|null>} { broker, message } on success, null on error
 */
export const ping = async () => {
    try {
        const data = await callBackendAPI('/ping');
        return data;
    } catch (error) {
        logger.warn('[AccountService] Ping failed:', error.message);
        return null;
    }
};

/**
 * Get Funds - Fetch account balance and margin details
 * @returns {Promise<Object|null>} { availablecash, collateral, m2mrealized, m2munrealized, utiliseddebits }
 */
export const getFunds = async () => {
    try {
        const data = await callBackendAPI('/funds');
        return data;
    } catch (error) {
        logger.error('[AccountService] Funds error:', error.message);
        return null;
    }
};

/**
 * Get Position Book - Fetch current open positions
 * @returns {Promise<Array>} Array of position objects
 */
export const getPositionBook = async () => {
    try {
        const data = await callBackendAPI('/positionbook');
        return data || [];
    } catch (error) {
        logger.error('[AccountService] PositionBook error:', error.message);
        return [];
    }
};

/**
 * Get Order Book - Fetch all orders with statistics
 * @returns {Promise<Object>} { orders: [], statistics: {} }
 */
export const getOrderBook = async () => {
    try {
        const data = await callBackendAPI('/orderbook');
        return data || { orders: [], statistics: {} };
    } catch (error) {
        logger.error('[AccountService] OrderBook error:', error.message);
        return { orders: [], statistics: {} };
    }
};

/**
 * Get Trade Book - Fetch executed trades
 * @returns {Promise<Array>} Array of trade objects
 */
export const getTradeBook = async () => {
    try {
        const data = await callBackendAPI('/tradebook');
        return data || [];
    } catch (error) {
        logger.error('[AccountService] TradeBook error:', error.message);
        return [];
    }
};

/**
 * Get Holdings - Fetch long-term stock holdings with P&L
 * @returns {Promise<Object>} { holdings: [], statistics: {} }
 */
export const getHoldings = async () => {
    try {
        const data = await callBackendAPI('/holdings');
        return data || { holdings: [], statistics: {} };
    } catch (error) {
        logger.error('[AccountService] Holdings error:', error.message);
        return { holdings: [], statistics: {} };
    }
};

/**
 * Place Order - Submit new order
 * @param {Object} orderParams - Order parameters
 * @returns {Promise<Object>} Order response with order ID
 */
export const placeOrder = async (orderParams) => {
    try {
        const data = await callBackendAPI('/placeorder', orderParams);
        logger.info('[AccountService] Order placed successfully:', data);
        
        // Emit event for data synchronization
        eventService.emit(Events.ORDER_PLACED, { order: data, params: orderParams });
        eventService.emit(Events.FUNDS_UPDATED);
        
        return data;
    } catch (error) {
        logger.error('[AccountService] PlaceOrder error:', error.message);
        throw error;
    }
};

/**
 * Modify Order - Update existing order
 * @param {Object} orderParams - Modified order parameters
 * @returns {Promise<Object>} Modification response
 */
export const modifyOrder = async (orderParams) => {
    try {
        const data = await callBackendAPI('/modifyorder', orderParams);
        logger.info('[AccountService] Order modified successfully:', data);
        
        // Emit event for data synchronization
        eventService.emit(Events.ORDER_MODIFIED, { order: data, params: orderParams });
        
        return data;
    } catch (error) {
        logger.error('[AccountService] ModifyOrder error:', error.message);
        throw error;
    }
};

/**
 * Cancel Order - Cancel pending order
 * @param {string} orderId - Order ID to cancel
 * @returns {Promise<Object>} Cancellation response
 */
export const cancelOrder = async (orderId) => {
    try {
        const data = await callBackendAPI('/cancelorder', { orderid: orderId });
        logger.info('[AccountService] Order cancelled successfully:', data);
        
        // Emit event for data synchronization
        eventService.emit(Events.ORDER_CANCELLED, { orderId, response: data });
        eventService.emit(Events.FUNDS_UPDATED);
        
        return data;
    } catch (error) {
        logger.error('[AccountService] CancelOrder error:', error.message);
        throw error;
    }
};

/**
 * Close Position - Exit position
 * @param {Object} positionParams - Position parameters
 * @returns {Promise<Object>} Exit response
 */
export const closePosition = async (positionParams) => {
    try {
        const data = await callBackendAPI('/closeposition', positionParams);
        logger.info('[AccountService] Position closed successfully:', data);
        
        // Emit events for data synchronization
        eventService.emit(Events.POSITION_CLOSED, { position: positionParams, response: data });
        eventService.emit(Events.FUNDS_UPDATED);
        eventService.emit(Events.TRADE_EXECUTED);
        
        return data;
    } catch (error) {
        logger.error('[AccountService] ClosePosition error:', error.message);
        throw error;
    }
};
