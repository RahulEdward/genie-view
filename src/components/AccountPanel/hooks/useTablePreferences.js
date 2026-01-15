import { useState, useEffect, useCallback } from 'react';

const STORAGE_KEY = 'openalgo_table_preferences';

const DEFAULT_PREFERENCES = {
    // Default column visibility or other settings can go here
    showClosedPositions: true,
    density: 'compact', // compact, standard, comfortable
    showPnlInPercent: false,
};

export const useTablePreferences = () => {
    const [preferences, setPreferences] = useState(() => {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            return stored ? { ...DEFAULT_PREFERENCES, ...JSON.parse(stored) } : DEFAULT_PREFERENCES;
        } catch (error) {
            console.warn('[useTablePreferences] Failed to load preferences:', error);
            return DEFAULT_PREFERENCES;
        }
    });

    const updatePreference = useCallback((key, value) => {
        setPreferences(prev => {
            const newPrefs = { ...prev, [key]: value };
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(newPrefs));
            } catch (error) {
                console.warn('[useTablePreferences] Failed to save preferences:', error);
            }
            return newPrefs;
        });
    }, []);

    // Reset to defaults
    const resetPreferences = useCallback(() => {
        setPreferences(DEFAULT_PREFERENCES);
        try {
            localStorage.removeItem(STORAGE_KEY);
        } catch (error) {
            console.warn('[useTablePreferences] Failed to reset preferences:', error);
        }
    }, []);

    return {
        preferences,
        updatePreference,
        resetPreferences
    };
};
