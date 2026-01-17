import { useState, useEffect, useRef } from 'react';
import openalgo from '../services/openalgo';
import logger from '../utils/logger';
import { useWorkspaceStore } from '../store/workspaceStore';

// Debounce delay in milliseconds (2 seconds for quicker UX)
const SYNC_DEBOUNCE_DELAY = 2000;

// Timeout for initial cloud sync fetch (5 seconds)
const CLOUD_FETCH_TIMEOUT = 5000;

// Keys to sync - all chart settings
const SYNC_KEYS = [
    // Core chart state
    'tv_saved_layout',       // Chart layout with indicators, symbol, interval per chart
    'tv_watchlists',         // Watchlists
    'tv_theme',              // Theme (dark/light)
    'tv_interval',           // Current interval/timeframe

    // Intervals
    'tv_fav_intervals_v2',   // Favorite intervals
    'tv_custom_intervals',   // Custom intervals
    'tv_last_nonfav_interval', // Last non-favorite interval

    // Chart appearance
    'tv_chart_appearance',   // Chart appearance (colors, candle style)
    'tv_drawing_defaults',   // Drawing tool defaults
    'tv_drawing_templates',  // Drawing templates
    'tv_favorite_drawing_tools', // Favorite drawing tools
    'tv_floating_toolbar_pos', // Floating toolbar position

    // Alerts
    'tv_alerts',             // Alerts
    'tv_alert_logs',         // Alert logs
    'tv_chart_alerts',       // Chart-specific alerts (per symbol)

    // Templates
    'tv_template_favorites', // Template favorites
    'tv_layout_templates',   // Layout templates
    'tv_chart_templates',    // Chart templates

    // Symbols
    'tv_symbol_favorites',   // Symbol favorites
    'tv_recent_symbols',     // Recent symbols

    // UI State
    'tv_recent_commands',    // Recent commands
    'tv_account_panel_open', // Account panel visibility
    'tv_watchlist_width',    // Watchlist panel width
    'tv_account_panel_height', // Account panel height
    'tv_show_oi_lines',      // OI lines toggle
    'tv_position_tracker_settings', // Position tracker settings

    // OpenAlgo settings
    'oa_session_break_visible', // Session break visibility setting
    'oa_timer_visible',      // Timer visibility setting
    'oa_sound_settings',     // Sound/notification settings
    'oa_custom_shortcuts',   // Custom keyboard shortcuts

    // Option chain
    'optionChainStrikeCount' // Option chain strike count preference
];


/**
 * Hook to manage Cloud Workspace Synchronization
 * - Blocks rendering until cloud sync is complete (or timeout) for authenticated users
 * - For non-authenticated users, allows immediate render
 * - Auto-saves changes to backend after 5s of inactivity
 * - Tracks which auth state we've loaded for to prevent flash during transitions
 * 
 * @param {boolean|null} isAuthenticated - null=checking, false=not auth, true=authenticated
 * @returns {{ isLoaded: boolean, isSyncing: boolean }}
 */
export const useCloudWorkspaceSync = (isAuthenticated) => {
    // Track which auth state we've completed loading for
    // This prevents flash during auth transitions
    // Uses a special 'uninitialized' symbol to distinguish from null/false/true
    const [loadedForAuth, setLoadedForAuth] = useState('uninitialized');
    const [isSyncing, setIsSyncing] = useState(false);

    // Get the setFromCloud action to hydrate store directly
    const setFromCloud = useWorkspaceStore(state => state.setFromCloud);

    // Store last SAVED state (confirmed by server)
    const lastSavedState = useRef({});
    const saveTimeoutRef = useRef(null);
    const hasLoadedFromServer = useRef(false);

    // Derive isLoaded from whether we've loaded for the CURRENT auth state
    // - When auth is still checking (null), isLoaded = false
    // - When loadedForAuth matches isAuthenticated (false or true), isLoaded = true
    // - During transitions, they won't match, so isLoaded = false
    const isLoaded = isAuthenticated !== null && loadedForAuth === isAuthenticated;

    // Initial Load - handles different auth states
    useEffect(() => {
        // Auth is still being checked - keep blocking
        if (isAuthenticated === null) {
            logger.debug('[CloudSync] Auth checking, waiting...');
            // Don't change loadedForAuth - stay in loading state
            return;
        }

        // Not authenticated - no cloud sync needed, show auth screen
        if (isAuthenticated === false) {
            logger.debug('[CloudSync] Not authenticated, skipping cloud sync');
            setLoadedForAuth(false);
            return;
        }

        // Already loaded from server, don't reload
        if (hasLoadedFromServer.current) {
            logger.debug('[CloudSync] Already loaded from server, skipping');
            setLoadedForAuth(true);
            return;
        }

        // Check if preferences were already loaded during login validation
        // This flag is set by ApiKeyDialog when it saves preferences from the validation response
        const cloudSyncDone = localStorage.getItem('_cloud_sync_done');
        if (cloudSyncDone === 'true') {
            logger.info('[CloudSync] Preferences already loaded during login, skipping fetch. Current Theme:', localStorage.getItem('tv_theme'));
            // Clear the flag for future sessions
            localStorage.removeItem('_cloud_sync_done');
            hasLoadedFromServer.current = true;
            // Initialize lastSavedState with current localStorage
            SYNC_KEYS.forEach(key => {
                lastSavedState.current[key] = localStorage.getItem(key);
            });

            // IMPORTANT: Hydrate the Zustand store from localStorage
            // ApiKeyDialog saved to localStorage but didn't update the store
            const savedLayout = localStorage.getItem('tv_saved_layout');
            if (savedLayout) {
                logger.info('[CloudSync] Hydrating workspace store from login-loaded data');
                setFromCloud(savedLayout);
            }

            setLoadedForAuth(true);
            // Ensure listeners (like ThemeContext) update
            window.dispatchEvent(new Event('cloud-sync-complete'));
            return;
        }

        // Authenticated - fetch cloud data before allowing render
        // IMPORTANT: Don't set loadedForAuth here - stay in loading state until sync completes
        hasLoadedFromServer.current = true;
        logger.info('[CloudSync] User authenticated, loading preferences from server...');

        let isCancelled = false;
        let timeoutId = null;

        const loadPreferences = async () => {
            try {
                // Create a fetch promise with timeout
                const fetchPromise = openalgo.fetchUserPreferences();
                const timeoutPromise = new Promise((resolve) => {
                    timeoutId = setTimeout(() => {
                        if (!isCancelled) {
                            logger.warn(`[CloudSync] Fetch timeout (${CLOUD_FETCH_TIMEOUT / 1000}s), proceeding with local state`);
                            resolve({ data: null, invalidApiKey: false, timeout: true });
                        }
                    }, CLOUD_FETCH_TIMEOUT);
                });

                // Race between fetch and timeout
                const result = await Promise.race([fetchPromise, timeoutPromise]);

                // Clear timeout if fetch won the race
                if (timeoutId) clearTimeout(timeoutId);
                isCancelled = true;

                logger.debug('[CloudSync] Server response:', result);

                // If API key is invalid, just log it and proceed with local state
                // (Upfront validation on login page handles the main validation)
                if (result.invalidApiKey) {
                    logger.warn('[CloudSync] Invalid API key detected, using local state');
                }

                const prefs = result.data;
                if (prefs && typeof prefs === 'object' && Object.keys(prefs).length > 0) {
                    // Apply cloud data to localStorage BEFORE allowing render
                    let appliedCount = 0;
                    Object.entries(prefs).forEach(([key, value]) => {
                        try {
                            if (value !== null && value !== undefined) {
                                localStorage.setItem(key, value);
                                lastSavedState.current[key] = value;
                                appliedCount++;
                            }
                        } catch (e) {
                            logger.error(`[CloudSync] Error applying key ${key}:`, e);
                        }
                    });

                    // Populate global cache for loadDrawings to use (avoids duplicate API calls)
                    if (!window._chartPrefsCache) window._chartPrefsCache = {};
                    Object.assign(window._chartPrefsCache, prefs);

                    logger.info(`[CloudSync] Applied ${appliedCount} preferences from cloud.`);

                    // CLOUD-FIRST: Hydrate store directly with layout data
                    // This updates the Zustand store without requiring a remount
                    if (prefs.tv_saved_layout) {
                        logger.info('[CloudSync] Hydrating workspace store from cloud data');
                        setFromCloud(prefs.tv_saved_layout);
                    }

                    // Dispatch event for contexts (like ThemeContext) that don't remount
                    window.dispatchEvent(new Event('cloud-sync-complete'));
                } else {
                    // No cloud data or timeout - use local state
                    logger.info('[CloudSync] No cloud preferences, using local state.');
                    SYNC_KEYS.forEach(key => {
                        lastSavedState.current[key] = localStorage.getItem(key);
                    });
                }
            } catch (error) {
                logger.error('[CloudSync] Failed to load preferences:', error);
                // Initialize lastSavedState with current localStorage
                SYNC_KEYS.forEach(key => {
                    lastSavedState.current[key] = localStorage.getItem(key);
                });
            }

            // Now allow AppContent to mount - localStorage is ready
            logger.info('[CloudSync] Cloud sync complete, allowing render');
            setLoadedForAuth(true);
        };

        loadPreferences();
    }, [isAuthenticated]);

    // EVENT-BASED Auto-Save using Zustand subscribe (replaces polling)
    // This is more efficient than polling - only triggers when actual changes occur
    useEffect(() => {
        if (isAuthenticated !== true || !isLoaded) return;

        // Debounced save function
        const scheduleSave = () => {
            // Collect all current values for sync keys
            const toSave = {};
            let hasChanges = false;

            SYNC_KEYS.forEach(key => {
                const currentValue = localStorage.getItem(key);
                const lastValue = lastSavedState.current[key];

                if (currentValue !== lastValue) {
                    if (currentValue == null && lastValue == null) return;
                    toSave[key] = currentValue || "";
                    hasChanges = true;
                }
            });

            if (!hasChanges) return;

            logger.debug('[CloudSync] Changes detected, scheduling save:', Object.keys(toSave));

            // Clear existing timeout
            if (saveTimeoutRef.current) {
                clearTimeout(saveTimeoutRef.current);
            }

            // Schedule debounced save
            saveTimeoutRef.current = setTimeout(async () => {
                // Re-collect changes at save time (in case more changes happened)
                const finalToSave = {};
                SYNC_KEYS.forEach(key => {
                    const currentValue = localStorage.getItem(key);
                    const lastValue = lastSavedState.current[key];
                    if (currentValue !== lastValue && !(currentValue == null && lastValue == null)) {
                        finalToSave[key] = currentValue || "";
                    }
                });

                if (Object.keys(finalToSave).length === 0) {
                    saveTimeoutRef.current = null;
                    return;
                }

                logger.info('[CloudSync] Executing auto-save for keys:', Object.keys(finalToSave));

                setIsSyncing(true);
                try {
                    const success = await openalgo.saveUserPreferences(finalToSave);
                    if (success) {
                        // Update last saved state
                        Object.entries(finalToSave).forEach(([key, val]) => {
                            lastSavedState.current[key] = val;
                        });
                        logger.info('[CloudSync] Auto-save complete!');
                    } else {
                        logger.error('[CloudSync] Auto-save returned false');
                    }
                } catch (err) {
                    logger.error('[CloudSync] Auto-save failed:', err);
                } finally {
                    setIsSyncing(false);
                    saveTimeoutRef.current = null;
                }
            }, SYNC_DEBOUNCE_DELAY);
        };

        // Subscribe to Zustand store changes (for workspace state)
        // This fires immediately when store state changes
        const unsubscribeStore = useWorkspaceStore.subscribe(
            (state) => ({ charts: state.charts, layout: state.layout, activeChartId: state.activeChartId }),
            (newState, prevState) => {
                // Only trigger if the values actually changed
                if (JSON.stringify(newState) !== JSON.stringify(prevState)) {
                    logger.debug('[CloudSync] Store change detected');
                    scheduleSave();
                }
            },
            { equalityFn: (a, b) => JSON.stringify(a) === JSON.stringify(b) }
        );

        // Also listen for storage events (for cross-tab sync and non-store keys)
        // Note: 'storage' event only fires in OTHER tabs, but this catches theme changes etc.
        const handleStorageEvent = (e) => {
            if (e.key && SYNC_KEYS.includes(e.key)) {
                logger.debug('[CloudSync] Storage event for:', e.key);
                scheduleSave();
            }
        };
        window.addEventListener('storage', handleStorageEvent);

        // Listen for custom local storage changes (same-tab, from other components)
        const handleLocalChange = () => {
            scheduleSave();
        };
        window.addEventListener('oa-settings-changed', handleLocalChange);

        return () => {
            unsubscribeStore();
            window.removeEventListener('storage', handleStorageEvent);
            window.removeEventListener('oa-settings-changed', handleLocalChange);
            if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
        };
    }, [isAuthenticated, isLoaded]);

    return { isLoaded, isSyncing };
};
