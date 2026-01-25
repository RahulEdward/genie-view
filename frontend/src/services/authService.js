/**
 * Authentication Service
 * Handles login, logout, and authentication state management
 */

import { callBackendAPI } from './apiService';
import { sharedWebSocket } from './angelalgo';
import logger from '../utils/logger';

const STORAGE_KEYS = {
    API_KEY: 'aa_apikey',
    BROKER: 'aa_broker',
    CLIENT_ID: 'aa_client_id'
};

/**
 * Login to broker via backend
 * @param {Object} credentials - Login credentials
 * @param {string} credentials.broker - Broker name (e.g., 'angelone')
 * @param {string} credentials.clientId - Client ID
 * @param {string} credentials.password - Password/PIN
 * @param {string} credentials.totp - TOTP code
 * @param {string} credentials.apiKey - API key
 * @param {string} credentials.totpSecret - Optional TOTP secret for auto-generation
 * @param {boolean} credentials.saveCredentials - Whether to save credentials
 * @returns {Promise<Object>} Login response with API key
 */
export const login = async (credentials) => {
    try {
        const response = await callBackendAPI('/auth/login', {
            broker: credentials.broker,
            client_id: credentials.clientId,
            password: credentials.password,
            totp: credentials.totp,
            api_key: credentials.apiKey,
            totp_secret: credentials.totpSecret || null,
            save_credentials: credentials.saveCredentials || false
        });

        if (response && response.apikey) {
            // Store API key and broker info in localStorage
            localStorage.setItem(STORAGE_KEYS.API_KEY, response.apikey);
            localStorage.setItem(STORAGE_KEYS.BROKER, response.broker);
            localStorage.setItem(STORAGE_KEYS.CLIENT_ID, response.client_id);

            // Connect WebSocket after successful login
            wsManager.connect();

            logger.info('[Auth] Login successful');
            return { success: true, apiKey: response.apikey };
        } else {
            throw new Error('Invalid login response');
        }
    } catch (error) {
        logger.error('[Auth] Login error:', error.message);
        throw error;
    }
};

/**
 * Quick login using saved credentials
 * @param {string} broker - Broker name
 * @param {string} clientId - Client ID
 * @param {string} totp - TOTP code
 * @returns {Promise<Object>} Login response with API key
 */
export const quickLogin = async (broker, clientId, totp) => {
    try {
        const response = await callBackendAPI('/auth/quick-login', {
            broker,
            client_id: clientId,
            totp
        });

        if (response && response.apikey) {
            // Store API key and broker info in localStorage
            localStorage.setItem(STORAGE_KEYS.API_KEY, response.apikey);
            localStorage.setItem(STORAGE_KEYS.BROKER, response.broker);
            localStorage.setItem(STORAGE_KEYS.CLIENT_ID, response.client_id);

            // Connect WebSocket after successful login
            wsManager.connect();

            logger.info('[Auth] Quick login successful');
            return { success: true, apiKey: response.apikey };
        } else {
            throw new Error('Invalid quick login response');
        }
    } catch (error) {
        logger.error('[Auth] Quick login error:', error.message);
        throw error;
    }
};

/**
 * Logout from broker
 * Clears stored credentials and disconnects WebSocket
 */
export const logout = async () => {
    try {
        // Call backend logout API (optional - backend may not have this endpoint)
        try {
            await callBackendAPI('/auth/logout');
        } catch (err) {
            // Ignore logout API errors - proceed with local cleanup
            logger.warn('[Auth] Logout API error (ignored):', err.message);
        }

        // Clear stored credentials
        localStorage.removeItem(STORAGE_KEYS.API_KEY);
        localStorage.removeItem(STORAGE_KEYS.BROKER);
        localStorage.removeItem(STORAGE_KEYS.CLIENT_ID);

        // Disconnect WebSocket
        wsManager.disconnect();

        logger.info('[Auth] Logout successful');
        return { success: true };
    } catch (error) {
        logger.error('[Auth] Logout error:', error.message);
        throw error;
    }
};

/**
 * Check if user is authenticated
 * @returns {boolean} True if API key exists in localStorage
 */
export const isAuthenticated = () => {
    const apiKey = localStorage.getItem(STORAGE_KEYS.API_KEY);
    return !!apiKey;
};

/**
 * Get stored API key
 * @returns {string|null} API key or null if not found
 */
export const getApiKey = () => {
    return localStorage.getItem(STORAGE_KEYS.API_KEY);
};

/**
 * Get stored broker name
 * @returns {string|null} Broker name or null if not found
 */
export const getBroker = () => {
    return localStorage.getItem(STORAGE_KEYS.BROKER);
};

/**
 * Get stored client ID
 * @returns {string|null} Client ID or null if not found
 */
export const getClientId = () => {
    return localStorage.getItem(STORAGE_KEYS.CLIENT_ID);
};

/**
 * Validate API key with backend
 * @returns {Promise<boolean>} True if API key is valid
 */
export const validateApiKey = async () => {
    try {
        const apiKey = getApiKey();
        if (!apiKey) {
            return false;
        }

        // Call a simple backend endpoint to validate API key
        // Using /funds as a test endpoint since it requires authentication
        await callBackendAPI('/funds');
        return true;
    } catch (error) {
        logger.error('[Auth] API key validation failed:', error.message);
        return false;
    }
};

/**
 * Get saved credentials from backend
 * @returns {Promise<Array>} Array of saved credential objects
 */
export const getSavedCredentials = async () => {
    try {
        const response = await callBackendAPI('/auth/credentials');
        return response || [];
    } catch (error) {
        logger.error('[Auth] Failed to fetch saved credentials:', error.message);
        return [];
    }
};

/**
 * Delete saved credentials
 * @param {string} broker - Broker name
 * @param {string} clientId - Client ID
 * @returns {Promise<boolean>} True if deletion was successful
 */
export const deleteSavedCredentials = async (broker, clientId) => {
    try {
        await callBackendAPI(`/auth/credentials/${broker}/${clientId}`, {}, 'DELETE');
        logger.info('[Auth] Deleted saved credentials for', broker, clientId);
        return true;
    } catch (error) {
        logger.error('[Auth] Failed to delete saved credentials:', error.message);
        return false;
    }
};

export default {
    login,
    quickLogin,
    logout,
    isAuthenticated,
    getApiKey,
    getBroker,
    getClientId,
    validateApiKey,
    getSavedCredentials,
    deleteSavedCredentials
};
