import React, { createContext, useState, useEffect, useContext, useCallback } from 'react';
import { getThemeType } from '../utils/chartTheme';

const ThemeContext = createContext();

export const ThemeProvider = ({ children }) => {
    const [theme, setTheme] = useState(() => {
        return localStorage.getItem('tv_theme') || 'dark';
    });

    // Re-sync theme from localStorage (called after cloud sync)
    const refreshFromStorage = useCallback(() => {
        const storedTheme = localStorage.getItem('tv_theme');
        if (storedTheme && storedTheme !== theme) {
            setTheme(storedTheme);
        }
    }, [theme]);

    // Listen for cloud sync completion to refresh theme
    useEffect(() => {
        const handleCloudSyncComplete = () => {
            refreshFromStorage();
        };

        // Listen for custom event dispatched after cloud sync
        window.addEventListener('cloud-sync-complete', handleCloudSyncComplete);

        // Also listen for storage events (cross-tab sync)
        const handleStorageChange = (e) => {
            if (e.key === 'tv_theme' && e.newValue) {
                setTheme(e.newValue);
            }
        };
        window.addEventListener('storage', handleStorageChange);

        return () => {
            window.removeEventListener('cloud-sync-complete', handleCloudSyncComplete);
            window.removeEventListener('storage', handleStorageChange);
        };
    }, [refreshFromStorage]);

    // Apply theme to document
    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('tv_theme', theme);
    }, [theme]);

    const toggleTheme = () => {
        setTheme(prev => (getThemeType(prev) === 'dark' ? 'light' : 'dark'));
    };

    return (
        <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
            {children}
        </ThemeContext.Provider>
    );
};

export const useTheme = () => {
    const context = useContext(ThemeContext);
    if (!context) {
        throw new Error('useTheme must be used within a ThemeProvider');
    }
    return context;
};
