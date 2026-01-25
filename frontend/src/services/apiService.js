/**
 * Unified API Service
 * Centralized service for all backend API calls
 * Handles authentication, error handling, and response validation
 */

import { getApiKey, getApiBase } from './apiConfig';
import logger from '../utils/logger';

/**
 * Call backend API with unified error handling
 * @param {string} endpoint - API endpoint (e.g., '/funds', '/quotes')
 * @param {Object} params - Request parameters
 * @param {Object} options - Additional fetch options
 * @returns {Promise<any>} API response data
 * @throws {Error} If API call fails
 */
export const callBackendAPI = async (endpoint, params = {}, options = {}) => {
    const apiKey = getApiKey();
    
    if (!apiKey || apiKey.trim() === '') {
        throw new Error('Not authenticated. Please login first.');
    }
    
    const url = `${getApiBase()}${endpoint}`;
    const requestBody = { apikey: apiKey, ...params };
    
    // Log request for debugging
    logger.debug('[API] Request:', { endpoint, params });
    
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            credentials: 'include',
            body: JSON.stringify(requestBody),
            ...options
        });
        
        // Log response status
        logger.debug('[API] Response status:', response.status);
        
        if (!response.ok) {
            // Handle HTTP errors
            if (response.status === 401) {
                throw new Error('Authentication failed. Please login again.');
            } else if (response.status === 429) {
                throw new Error('Rate limit exceeded. Please try again later.');
            } else if (response.status === 500) {
                throw new Error('Server error. Please try again later.');
            } else {
                throw new Error(`API error: ${response.status} ${response.statusText}`);
            }
        }
        
        const data = await response.json();
        
        // Log response data
        logger.debug('[API] Response data:', data);
        
        // Validate response format
        if (!data || typeof data !== 'object') {
            throw new Error('Invalid response format from server');
        }
        
        // Check status field
        if (data.status !== 'success') {
            const errorMessage = data.message || 'API call failed';
            throw new Error(errorMessage);
        }
        
        // Return data field
        return data.data;
        
    } catch (error) {
        // Log error
        logger.error('[API] Error:', { endpoint, error: error.message });
        
        // Re-throw with context
        if (error.message.includes('fetch')) {
            throw new Error('Network error. Please check your connection.');
        }
        
        throw error;
    }
};

/**
 * Call backend API without authentication (for public endpoints)
 * @param {string} endpoint - API endpoint
 * @param {Object} params - Request parameters
 * @param {Object} options - Additional fetch options
 * @returns {Promise<any>} API response data
 */
export const callPublicAPI = async (endpoint, params = {}, options = {}) => {
    const url = `${getApiBase()}${endpoint}`;
    
    logger.debug('[API] Public request:', { endpoint, params });
    
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            credentials: 'include',
            body: JSON.stringify(params),
            ...options
        });
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (data.status !== 'success') {
            throw new Error(data.message || 'API call failed');
        }
        
        return data.data;
        
    } catch (error) {
        logger.error('[API] Public API error:', { endpoint, error: error.message });
        throw error;
    }
};

/**
 * Batch API call helper
 * Makes multiple API calls in parallel
 * @param {Array<{endpoint: string, params: Object}>} requests - Array of requests
 * @returns {Promise<Array>} Array of responses
 */
export const batchAPICall = async (requests) => {
    logger.debug('[API] Batch request:', { count: requests.length });
    
    try {
        const promises = requests.map(({ endpoint, params }) =>
            callBackendAPI(endpoint, params)
        );
        
        const results = await Promise.allSettled(promises);
        
        return results.map((result, index) => {
            if (result.status === 'fulfilled') {
                return { success: true, data: result.value };
            } else {
                logger.error('[API] Batch request failed:', {
                    endpoint: requests[index].endpoint,
                    error: result.reason.message
                });
                return { success: false, error: result.reason.message };
            }
        });
        
    } catch (error) {
        logger.error('[API] Batch call error:', error.message);
        throw error;
    }
};

/**
 * Test backend connection
 * @param {string} backendUrl - Backend URL to test (optional, uses current if not provided)
 * @returns {Promise<Object>} Connection test result
 */
export const testBackendConnection = async (backendUrl = null) => {
    const testUrl = backendUrl ? `${backendUrl}/api/v1/ping` : `${getApiBase()}/ping`;
    
    logger.debug('[API] Testing connection:', testUrl);
    
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout
        
        const response = await fetch(testUrl, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            },
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            return {
                success: false,
                message: `Connection failed: ${response.status} ${response.statusText}`
            };
        }
        
        const data = await response.json();
        
        return {
            success: true,
            message: 'Connection successful',
            version: data.version || 'unknown',
            timestamp: data.timestamp || new Date().toISOString()
        };
        
    } catch (error) {
        logger.error('[API] Connection test failed:', error.message);
        
        if (error.name === 'AbortError') {
            return {
                success: false,
                message: 'Connection timeout. Please check if backend is running.'
            };
        }
        
        return {
            success: false,
            message: `Connection failed: ${error.message}`
        };
    }
};

export default {
    callBackendAPI,
    callPublicAPI,
    batchAPICall,
    testBackendConnection
};
