/**
 * Error Handler Utility
 * Centralized error handling for API, WebSocket, and Network errors
 */

import logger from './logger';

// Error code to user-friendly message mapping
const ERROR_MESSAGES = {
    // Authentication errors
    'AUTH_FAILED': 'Authentication failed. Please check your credentials.',
    'INVALID_API_KEY': 'Invalid API key. Please login again.',
    'SESSION_EXPIRED': 'Your session has expired. Please login again.',
    'UNAUTHORIZED': 'Unauthorized access. Please login.',
    
    // Network errors
    'NETWORK_ERROR': 'Network error. Please check your internet connection.',
    'TIMEOUT': 'Request timed out. Please try again.',
    'CONNECTION_REFUSED': 'Could not connect to server. Please check if backend is running.',
    
    // API errors
    'API_ERROR': 'An error occurred while processing your request.',
    'INVALID_REQUEST': 'Invalid request. Please check your input.',
    'RATE_LIMIT': 'Too many requests. Please wait a moment and try again.',
    'SERVER_ERROR': 'Server error. Please try again later.',
    
    // WebSocket errors
    'WS_CONNECTION_FAILED': 'WebSocket connection failed. Retrying...',
    'WS_DISCONNECTED': 'WebSocket disconnected. Reconnecting...',
    'WS_AUTH_FAILED': 'WebSocket authentication failed.',
    
    // Broker errors
    'BROKER_ERROR': 'Broker API error. Please try again.',
    'INSUFFICIENT_FUNDS': 'Insufficient funds for this order.',
    'INVALID_SYMBOL': 'Invalid symbol. Please check the symbol name.',
    'MARKET_CLOSED': 'Market is closed. Trading is not allowed.',
    'ORDER_REJECTED': 'Order was rejected by the broker.',
    
    // Data errors
    'NO_DATA': 'No data available for the requested period.',
    'INVALID_DATA': 'Invalid data received from server.',
    'PARSE_ERROR': 'Error parsing server response.',
    
    // Default
    'UNKNOWN_ERROR': 'An unknown error occurred. Please try again.'
};

/**
 * Get user-friendly error message from error code
 * @param {string} code - Error code
 * @returns {string} User-friendly error message
 */
const getErrorMessage = (code) => {
    return ERROR_MESSAGES[code] || ERROR_MESSAGES.UNKNOWN_ERROR;
};

/**
 * Extract error code from error object
 * @param {Error|Object} error - Error object
 * @returns {string} Error code
 */
const extractErrorCode = (error) => {
    if (!error) return 'UNKNOWN_ERROR';
    
    // Check for explicit error code
    if (error.code) return error.code;
    
    // Check for HTTP status codes
    if (error.status) {
        switch (error.status) {
            case 401: return 'UNAUTHORIZED';
            case 403: return 'UNAUTHORIZED';
            case 404: return 'API_ERROR';
            case 429: return 'RATE_LIMIT';
            case 500: return 'SERVER_ERROR';
            case 502: return 'SERVER_ERROR';
            case 503: return 'SERVER_ERROR';
            default: return 'API_ERROR';
        }
    }
    
    // Check error message for common patterns
    const message = error.message?.toLowerCase() || '';
    if (message.includes('network')) return 'NETWORK_ERROR';
    if (message.includes('timeout')) return 'TIMEOUT';
    if (message.includes('refused')) return 'CONNECTION_REFUSED';
    if (message.includes('unauthorized') || message.includes('auth')) return 'UNAUTHORIZED';
    if (message.includes('websocket') || message.includes('ws')) return 'WS_CONNECTION_FAILED';
    
    return 'UNKNOWN_ERROR';
};

/**
 * Handle API errors
 * @param {Error} error - Error object from API call
 * @param {Object} options - Options for error handling
 * @param {boolean} options.showToast - Whether to show toast notification
 * @param {Function} options.onError - Custom error handler callback
 * @returns {Object} Processed error object with user-friendly message
 */
export const handleApiError = (error, options = {}) => {
    const { showToast = true, onError } = options;
    
    logger.error('[ErrorHandler] API Error:', error);
    
    const errorCode = extractErrorCode(error);
    const userMessage = getErrorMessage(errorCode);
    
    const processedError = {
        code: errorCode,
        message: userMessage,
        originalError: error,
        timestamp: new Date().toISOString()
    };
    
    // Show toast notification if enabled
    if (showToast && window.dispatchEvent) {
        window.dispatchEvent(new CustomEvent('oa-show-toast', {
            detail: { message: userMessage, type: 'error' }
        }));
    }
    
    // Call custom error handler if provided
    if (onError && typeof onError === 'function') {
        onError(processedError);
    }
    
    return processedError;
};

/**
 * Handle WebSocket errors
 * @param {Error} error - Error object from WebSocket
 * @param {Object} options - Options for error handling
 * @param {boolean} options.showToast - Whether to show toast notification
 * @param {Function} options.onError - Custom error handler callback
 * @returns {Object} Processed error object with user-friendly message
 */
export const handleWebSocketError = (error, options = {}) => {
    const { showToast = false, onError } = options; // Default to false for WS errors (too noisy)
    
    logger.error('[ErrorHandler] WebSocket Error:', error);
    
    const errorCode = error.code || 'WS_CONNECTION_FAILED';
    const userMessage = getErrorMessage(errorCode);
    
    const processedError = {
        code: errorCode,
        message: userMessage,
        originalError: error,
        timestamp: new Date().toISOString()
    };
    
    // Show toast notification if enabled
    if (showToast && window.dispatchEvent) {
        window.dispatchEvent(new CustomEvent('oa-show-toast', {
            detail: { message: userMessage, type: 'warning' }
        }));
    }
    
    // Call custom error handler if provided
    if (onError && typeof onError === 'function') {
        onError(processedError);
    }
    
    return processedError;
};

/**
 * Handle Network errors
 * @param {Error} error - Error object from network request
 * @param {Object} options - Options for error handling
 * @param {boolean} options.showToast - Whether to show toast notification
 * @param {Function} options.onError - Custom error handler callback
 * @returns {Object} Processed error object with user-friendly message
 */
export const handleNetworkError = (error, options = {}) => {
    const { showToast = true, onError } = options;
    
    logger.error('[ErrorHandler] Network Error:', error);
    
    const errorCode = 'NETWORK_ERROR';
    const userMessage = getErrorMessage(errorCode);
    
    const processedError = {
        code: errorCode,
        message: userMessage,
        originalError: error,
        timestamp: new Date().toISOString()
    };
    
    // Show toast notification if enabled
    if (showToast && window.dispatchEvent) {
        window.dispatchEvent(new CustomEvent('oa-show-toast', {
            detail: { message: userMessage, type: 'error' }
        }));
    }
    
    // Call custom error handler if provided
    if (onError && typeof onError === 'function') {
        onError(processedError);
    }
    
    return processedError;
};

/**
 * Handle generic errors
 * @param {Error} error - Error object
 * @param {Object} options - Options for error handling
 * @returns {Object} Processed error object
 */
export const handleError = (error, options = {}) => {
    // Determine error type and route to appropriate handler
    if (error.name === 'NetworkError' || error.message?.includes('fetch')) {
        return handleNetworkError(error, options);
    }
    
    if (error.name === 'WebSocketError' || error.message?.includes('WebSocket')) {
        return handleWebSocketError(error, options);
    }
    
    // Default to API error handler
    return handleApiError(error, options);
};

/**
 * Check if error is retryable
 * @param {Error} error - Error object
 * @returns {boolean} True if error is retryable
 */
export const isRetryableError = (error) => {
    const errorCode = extractErrorCode(error);
    const retryableCodes = [
        'NETWORK_ERROR',
        'TIMEOUT',
        'SERVER_ERROR',
        'WS_CONNECTION_FAILED',
        'WS_DISCONNECTED'
    ];
    
    return retryableCodes.includes(errorCode);
};

/**
 * Check if error requires re-authentication
 * @param {Error} error - Error object
 * @returns {boolean} True if re-authentication is required
 */
export const requiresReauth = (error) => {
    const errorCode = extractErrorCode(error);
    const reauthCodes = [
        'UNAUTHORIZED',
        'INVALID_API_KEY',
        'SESSION_EXPIRED',
        'AUTH_FAILED'
    ];
    
    return reauthCodes.includes(errorCode);
};

export default {
    handleApiError,
    handleWebSocketError,
    handleNetworkError,
    handleError,
    isRetryableError,
    requiresReauth,
    getErrorMessage
};
