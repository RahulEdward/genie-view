import React, { useEffect, useRef } from 'react';
import styles from './PriceScaleMenu.module.css';
import { useUser } from '../../context/UserContext';

// Icons
const AlertIcon = () => (
    <svg viewBox="0 0 18 18" width="18" height="18" fill="currentColor">
        <path d="M9 16c.83 0 1.5-.67 1.5-1.5h-3c0 .83.67 1.5 1.5 1.5zm4.5-4.5V8c0-2.43-1.72-4.44-4-4.9V2.5c0-.55-.45-1-1-1s-1 .45-1 1v.6c-2.28.46-4 2.47-4 4.9v3.5L2 13v.5h14V13l-1.5-1.5z" />
    </svg>
);

const SellIcon = () => (
    <svg viewBox="0 0 18 18" width="18" height="18" fill="currentColor">
        <path d="M9 4l-4 4h3v6h2V8h3z" transform="rotate(180 9 9)" />
    </svg>
);

const BuyIcon = () => (
    <svg viewBox="0 0 18 18" width="18" height="18" fill="currentColor">
        <path d="M9 4l-4 4h3v6h2V8h3z" />
    </svg>
);

const OrderIcon = () => (
    <svg viewBox="0 0 18 18" width="18" height="18" fill="currentColor">
        <path d="M3 3h12v2H3V3zm0 4h12v2H3V7zm0 4h8v2H3v-2zm10 0h2v4h-2v-4zm-2 2h6v2h-6v-2z" />
    </svg>
);

const HorizontalLineIcon = () => (
    <svg viewBox="0 0 18 18" width="18" height="18" fill="currentColor">
        <path d="M2 9h14v1H2V9z" />
        <circle cx="9" cy="9.5" r="1.5" />
    </svg>
);

/**
 * PriceScaleMenu - A context menu that appears when clicking the + button on the price scale
 * Provides options to add an alert, trade, or draw a horizontal line at the clicked price
 */
const PriceScaleMenu = ({
    visible,
    x,
    y,
    price,
    symbol,
    ltp = null,
    onAddAlert,
    onPlaceSellOrder,
    onPlaceBuyOrder,
    onAddOrder,
    onDrawHorizontalLine,
    onClose
}) => {
    const menuRef = useRef(null);
    const { isAuthenticated } = useUser();

    // Close menu when clicking outside (left or right click)
    useEffect(() => {
        if (!visible) return;

        const handleClickOutside = (e) => {
            if (menuRef.current && !menuRef.current.contains(e.target)) {
                onClose();
            }
        };

        const handleKeyDown = (e) => {
            if (e.key === 'Escape') {
                onClose();
            }
        };

        // Delay adding listener to avoid immediate close from the triggering click
        const timeoutId = setTimeout(() => {
            // Use capture phase to catch events before they reach the chart canvas
            document.addEventListener('mousedown', handleClickOutside, true);
            document.addEventListener('contextmenu', handleClickOutside, true);
            document.addEventListener('keydown', handleKeyDown);
        }, 0);

        return () => {
            clearTimeout(timeoutId);
            document.removeEventListener('mousedown', handleClickOutside, true);
            document.removeEventListener('contextmenu', handleClickOutside, true);
            document.removeEventListener('keydown', handleKeyDown);
        };
    }, [visible, onClose]);

    if (!visible) return null;

    // Format price for display
    const formattedPrice = price?.toLocaleString('en-IN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }) ?? '0.00';

    // Determine if clicked price is above or below LTP
    const isAboveLTP = ltp != null && price != null && price > ltp;
    const isBelowLTP = ltp != null && price != null && price < ltp;

    return (
        <div
            ref={menuRef}
            className={styles.menu}
            style={{
                left: x,
                top: y,
                transform: 'translate(-100%, -50%)' // Position to the left and center vertically
            }}
        >
            {/* Add Alert */}
            <button
                className={styles.menuItem}
                onClick={() => {
                    onAddAlert();
                    onClose();
                }}
            >
                <div className={styles.menuItemContent}>
                    <div className={styles.menuItemIcon}><AlertIcon /></div>
                    <span className={styles.menuItemText}>
                        Add alert on {symbol} at {formattedPrice}
                    </span>
                </div>
                <span className={styles.menuItemShortcut}>Alt+A</span>
            </button>

            {/* Trading Options (Authenticated only) */}
            {isAuthenticated && (
                <>
                    <div style={{ height: 1, backgroundColor: '#e0e3eb', margin: '4px 0' }} />

                    {/* First order option */}
                    <button
                        className={styles.menuItem}
                        onClick={() => {
                            if (isAboveLTP || !isBelowLTP) {
                                // Above LTP or same: Sell Limit
                                onPlaceSellOrder?.(price, 'LIMIT');
                            } else {
                                // Below LTP: Buy Limit
                                onPlaceBuyOrder?.(price, 'LIMIT');
                            }
                            onClose();
                        }}
                    >
                        <div className={styles.menuItemContent}>
                            <div className={styles.menuItemIcon}>{isAboveLTP || !isBelowLTP ? <SellIcon /> : <BuyIcon />}</div>
                            <span className={styles.menuItemText}>
                                {isAboveLTP || !isBelowLTP
                                    ? `Sell 1 ${symbol} @ ${formattedPrice} limit`
                                    : `Buy 1 ${symbol} @ ${formattedPrice} limit`
                                }
                            </span>
                        </div>
                        <span className={styles.menuItemShortcut}>{isAboveLTP || !isBelowLTP ? 'Alt+Shift+S' : 'Alt+Shift+B'}</span>
                    </button>

                    {/* Second order option */}
                    <button
                        className={styles.menuItem}
                        onClick={() => {
                            if (isAboveLTP || !isBelowLTP) {
                                // Above LTP or same: Buy Stop
                                onPlaceBuyOrder?.(price, 'SL');
                            } else {
                                // Below LTP: Sell Stop
                                onPlaceSellOrder?.(price, 'SL');
                            }
                            onClose();
                        }}
                    >
                        <div className={styles.menuItemContent}>
                            <div className={styles.menuItemIcon}>{isAboveLTP || !isBelowLTP ? <BuyIcon /> : <SellIcon />}</div>
                            <span className={styles.menuItemText}>
                                {isAboveLTP || !isBelowLTP
                                    ? `Buy 1 ${symbol} @ ${formattedPrice} stop`
                                    : `Sell 1 ${symbol} @ ${formattedPrice} stop`
                                }
                            </span>
                        </div>
                    </button>

                    {/* Add Order */}
                    <button
                        className={styles.menuItem}
                        onClick={() => {
                            onAddOrder?.(price);
                            onClose();
                        }}
                    >
                        <div className={styles.menuItemContent}>
                            <div className={styles.menuItemIcon}><OrderIcon /></div>
                            <span className={styles.menuItemText}>
                                Add order on {symbol} at {formattedPrice}...
                            </span>
                        </div>
                        <span className={styles.menuItemShortcut}>Shift+T</span>
                    </button>
                </>
            )}

            <div style={{ height: 1, backgroundColor: '#e0e3eb', margin: '4px 0' }} />

            {/* Draw Horizontal Line */}
            <button
                className={styles.menuItem}
                onClick={() => {
                    onDrawHorizontalLine();
                    onClose();
                }}
            >
                <div className={styles.menuItemContent}>
                    <div className={styles.menuItemIcon}><HorizontalLineIcon /></div>
                    <span className={styles.menuItemText}>
                        Draw Horizontal Line at {formattedPrice}
                    </span>
                </div>
                <span className={styles.menuItemShortcut}>Alt+H</span>
            </button>
        </div>
    );
};

export default PriceScaleMenu;
