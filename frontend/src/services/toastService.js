/**
 * Toast Notification Service
 * Centralized service for showing toast notifications
 * Uses the existing custom toast system in App.jsx via CustomEvent
 */

import logger from '../utils/logger';

/**
 * Show a toast notification
 * @param {string} message - Message to display
 * @param {string} type - Toast type: 'success', 'error', 'info', 'warning'
 * @param {Object} action - Optional action button config { label, onClick }
 */
const showToast = (message, type = 'info', action = null) => {
    if (!message) {
        logger.warn('[ToastService] Attempted to show toast with empty message');
        return;
    }

    // Dispatch custom event that App.jsx listens to
    if (window.dispatchEvent) {
        window.dispatchEvent(new CustomEvent('oa-show-toast', {
            detail: { message, type, action }
        }));
    } else {
        // Fallback to console if event system not available
        logger.warn('[ToastService] Event system not available, logging to console:', message);
        console.log(`[${type.toUpperCase()}] ${message}`);
    }
};

/**
 * Show success toast
 * @param {string} message - Success message
 * @param {Object} action - Optional action button
 */
export const success = (message, action = null) => {
    showToast(message, 'success', action);
};

/**
 * Show error toast
 * @param {string} message - Error message
 * @param {Object} action - Optional action button
 */
export const error = (message, action = null) => {
    showToast(message, 'error', action);
};

/**
 * Show info toast
 * @param {string} message - Info message
 * @param {Object} action - Optional action button
 */
export const info = (message, action = null) => {
    showToast(message, 'info', action);
};

/**
 * Show warning toast
 * @param {string} message - Warning message
 * @param {Object} action - Optional action button
 */
export const warning = (message, action = null) => {
    showToast(message, 'warning', action);
};

/**
 * Show toast with custom configuration
 * @param {Object} config - Toast configuration
 * @param {string} config.message - Message to display
 * @param {string} config.type - Toast type
 * @param {Object} config.action - Optional action button
 */
export const show = (config) => {
    const { message, type = 'info', action = null } = config;
    showToast(message, type, action);
};

// Export default object with all methods
export default {
    success,
    error,
    info,
    warning,
    show
};
