/**
 * ChartContextMenu Component
 * Displays the right-click context menu for chart interactions
 * TradingView-style comprehensive context menu
 */

import React, { useCallback, useEffect, useRef } from 'react';
import styles from './ChartContextMenu.module.css';
import { useUser } from '../../context/UserContext';

// Icons for menu items
const ResetIcon = () => (
    <svg viewBox="0 0 18 18" width="18" height="18" fill="currentColor">
        <path d="M9 3.5V1L5.5 4.5 9 8V5.5c2.49 0 4.5 2.01 4.5 4.5s-2.01 4.5-4.5 4.5S4.5 12.49 4.5 10H3c0 3.31 2.69 6 6 6s6-2.69 6-6-2.69-6-6-6z" />
    </svg>
);

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

const LockIcon = () => (
    <svg viewBox="0 0 18 18" width="18" height="18" fill="currentColor">
        <path d="M14 8h-1V6c0-2.21-1.79-4-4-4S5 3.79 5 6v2H4c-.55 0-1 .45-1 1v8c0 .55.45 1 1 1h10c.55 0 1-.45 1-1V9c0-.55-.45-1-1-1zM6.5 6c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5v2h-5V6zM14 17H4V9h10v8zm-5-3c.83 0 1.5-.67 1.5-1.5S9.83 11 9 11s-1.5.67-1.5 1.5S8.17 14 9 14z" />
    </svg>
);

const ObjectTreeIcon = () => (
    <svg viewBox="0 0 18 18" width="18" height="18" fill="currentColor">
        <path d="M3 3h4v4H3V3zm0 6h4v4H3V9zm6-6h6v4H9V3zm0 6h6v4H9V9z" />
    </svg>
);

const RemoveIcon = () => (
    <svg viewBox="0 0 18 18" width="18" height="18" fill="currentColor">
        <path d="M14 5H4v10h10V5zm-2 7H6v-1h6v1zM5 4h8v1H5V4z" />
    </svg>
);

const SettingsIcon = () => (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
        <path d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58a.49.49 0 00.12-.61l-1.92-3.32a.488.488 0 00-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.484.484 0 00-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58a.49.49 0 00-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z" />
    </svg>
);

const CopyIcon = () => (
    <svg viewBox="0 0 18 18" width="18" height="18" fill="currentColor">
        <path d="M12 1H4c-1.1 0-2 .9-2 2v10h2V3h8V1zm3 4H8c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h7c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 12H8V7h7v10z" />
    </svg>
);

/**
 * Chart right-click context menu
 * @param {Object} props
 * @param {boolean} props.show - Whether the menu is visible
 * @param {number} props.x - X coordinate position
 * @param {number} props.y - Y coordinate position
 * @param {string} props.orderId - Order ID (for cancel order option)
 * @param {string} props.symbol - Current symbol
 * @param {string} props.exchange - Current exchange
 * @param {number} props.price - Price at click point
 * @param {number} props.indicatorCount - Number of active indicators
 * @param {boolean} props.isVerticalCursorLocked - Whether vertical cursor is locked
 * @param {Function} props.onCancelOrder - Callback for cancel order
 * @param {Function} props.onOpenOptionChain - Callback for opening option chain
 * @param {Function} props.onResetChartView - Callback to reset chart view
 * @param {Function} props.onCopyPrice - Callback to copy price
 * @param {Function} props.onAddAlert - Callback to add alert
 * @param {Function} props.onPlaceSellOrder - Callback for sell limit order
 * @param {Function} props.onPlaceBuyOrder - Callback for buy stop order
 * @param {Function} props.onAddOrder - Callback for add order dialog
 * @param {Function} props.onToggleCursorLock - Callback to toggle cursor lock
 * @param {Function} props.onOpenObjectTree - Callback to open object tree
 * @param {Function} props.onRemoveIndicator - Callback to remove indicator
 * @param {Function} props.onOpenSettings - Callback to open settings
 * @param {Function} props.onClose - Callback to close the menu
 */
const ChartContextMenu = ({
    show,
    x,
    y,
    orderId,
    symbol,
    exchange,
    price,
    ltp = null, // Current Last Traded Price for dynamic order options
    indicatorCount = 0,
    isVerticalCursorLocked = false,
    onCancelOrder,
    onOpenOptionChain,
    onResetChartView,
    onCopyPrice,
    onAddAlert,
    onPlaceSellOrder,
    onPlaceBuyOrder,
    onAddOrder,
    onToggleCursorLock,
    onOpenObjectTree,
    onRemoveIndicator,
    onOpenSettings,
    onClose
}) => {
    const menuRef = useRef(null);
    const { isAuthenticated } = useUser();

    // Determine if clicked price is above or below LTP
    const isAboveLTP = ltp != null && price != null && price > ltp;
    const isBelowLTP = ltp != null && price != null && price < ltp;

    // Format price for display
    const formattedPrice = price != null ? price.toLocaleString('en-IN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }) : '—';

    // Adjust menu position to stay within viewport
    useEffect(() => {
        if (show && menuRef.current) {
            const rect = menuRef.current.getBoundingClientRect();
            const viewportWidth = window.innerWidth;
            const viewportHeight = window.innerHeight;

            let adjustedX = x;
            let adjustedY = y;

            // Adjust horizontal position if menu goes off right edge
            if (x + rect.width > viewportWidth) {
                adjustedX = viewportWidth - rect.width - 10;
            }

            // Adjust vertical position if menu goes off bottom edge
            if (y + rect.height > viewportHeight) {
                adjustedY = viewportHeight - rect.height - 10;
            }

            menuRef.current.style.left = `${adjustedX}px`;
            menuRef.current.style.top = `${adjustedY}px`;
        }
    }, [show, x, y]);

    const handleCopyPrice = useCallback(() => {
        if (price != null) {
            // Copy price with exactly 2 decimal places
            const formattedPriceToCopy = price.toFixed(2);
            navigator.clipboard.writeText(formattedPriceToCopy);
            onCopyPrice?.(price);
        }
        onClose();
    }, [price, onCopyPrice, onClose]);

    if (!show) return null;

    return (
        <div
            ref={menuRef}
            className={styles.contextMenu}
            style={{ left: x, top: y }}
            onClick={(e) => e.stopPropagation()}
        >
            {/* Reset Chart View */}
            <button
                className={styles.contextMenuItem}
                onClick={() => {
                    onResetChartView?.();
                    onClose();
                }}
            >
                <span className={styles.menuIcon}><ResetIcon /></span>
                <span className={styles.menuLabel}>Reset chart view</span>
                <span className={styles.menuShortcut}>Alt + R</span>
            </button>

            <div className={styles.divider} />

            {/* Copy Price */}
            <button
                className={styles.contextMenuItem}
                onClick={handleCopyPrice}
            >
                <span className={styles.menuIcon}><CopyIcon /></span>
                <span className={styles.menuLabel}>Copy price {formattedPrice}</span>
            </button>

            {/* Paste */}
            <button
                className={styles.contextMenuItem}
                onClick={() => {
                    // Paste functionality - reads from clipboard and could be used for drawing coordinates
                    navigator.clipboard.readText().then(text => {
                        console.log('Pasted:', text);
                    }).catch(err => {
                        console.warn('Failed to read clipboard:', err);
                    });
                    onClose();
                }}
            >
                <span className={styles.menuIcon}></span>
                <span className={styles.menuLabel}>Paste</span>
                <span className={styles.menuShortcut}>Ctrl + V</span>
            </button>

            <div className={styles.divider} />

            {/* Add Alert */}
            <button
                className={styles.contextMenuItem}
                onClick={() => {
                    onAddAlert?.(price);
                    onClose();
                }}
            >
                <span className={styles.menuIcon}><AlertIcon /></span>
                <span className={styles.menuLabel}>Add alert on {symbol} at {formattedPrice}...</span>
                <span className={styles.menuShortcut}>Alt + A</span>
            </button>

            {/* Trading options - only show when authenticated */}
            {isAuthenticated && (
                <>
                    {/* Above LTP: Sell Limit first, then Buy Stop */}
                    {/* Below LTP: Buy Limit first, then Sell Stop */}

                    {/* First order option */}
                    <button
                        className={styles.contextMenuItem}
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
                        <span className={styles.menuIcon}>{isAboveLTP || !isBelowLTP ? <SellIcon /> : <BuyIcon />}</span>
                        <span className={styles.menuLabel}>
                            {isAboveLTP || !isBelowLTP
                                ? `Sell 1 ${symbol} @ ${formattedPrice} limit`
                                : `Buy 1 ${symbol} @ ${formattedPrice} limit`
                            }
                        </span>
                        <span className={styles.menuShortcut}>{isAboveLTP || !isBelowLTP ? 'Alt + Shift + S' : 'Alt + Shift + B'}</span>
                    </button>

                    {/* Second order option */}
                    <button
                        className={styles.contextMenuItem}
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
                        <span className={styles.menuIcon}>{isAboveLTP || !isBelowLTP ? <BuyIcon /> : <SellIcon />}</span>
                        <span className={styles.menuLabel}>
                            {isAboveLTP || !isBelowLTP
                                ? `Buy 1 ${symbol} @ ${formattedPrice} stop`
                                : `Sell 1 ${symbol} @ ${formattedPrice} stop`
                            }
                        </span>
                    </button>

                    {/* Add Order */}
                    <button
                        className={styles.contextMenuItem}
                        onClick={() => {
                            onAddOrder?.(price);
                            onClose();
                        }}
                    >
                        <span className={styles.menuIcon}><OrderIcon /></span>
                        <span className={styles.menuLabel}>Add order on {symbol} at {formattedPrice}...</span>
                        <span className={styles.menuShortcut}>Shift + T</span>
                    </button>
                </>
            )}

            <div className={styles.divider} />

            {/* Lock Vertical Cursor Line */}
            <button
                className={`${styles.contextMenuItem} ${isVerticalCursorLocked ? styles.active : ''}`}
                onClick={() => {
                    onToggleCursorLock?.();
                    onClose();
                }}
            >
                <span className={styles.menuIcon}><LockIcon /></span>
                <span className={styles.menuLabel}>Lock vertical cursor line by time</span>
                {isVerticalCursorLocked && <span className={styles.checkmark}>✓</span>}
            </button>

            <div className={styles.divider} />

            {/* Object Tree */}
            <button
                className={styles.contextMenuItem}
                onClick={() => {
                    onOpenObjectTree?.();
                    onClose();
                }}
            >
                <span className={styles.menuIcon}><ObjectTreeIcon /></span>
                <span className={styles.menuLabel}>Object Tree...</span>
            </button>

            {/* Remove Indicator - only show if there are indicators */}
            {indicatorCount > 0 && (
                <button
                    className={styles.contextMenuItem}
                    onClick={() => {
                        onRemoveIndicator?.();
                        onClose();
                    }}
                >
                    <span className={styles.menuIcon}><RemoveIcon /></span>
                    <span className={styles.menuLabel}>Remove {indicatorCount} indicator{indicatorCount > 1 ? 's' : ''}</span>
                </button>
            )}

            {/* Cancel Order - only show when there's an order */}
            {orderId && (
                <>
                    <div className={styles.divider} />
                    <button
                        className={`${styles.contextMenuItem} ${styles.danger}`}
                        onClick={() => {
                            onCancelOrder?.(orderId);
                            onClose();
                        }}
                    >
                        Cancel Order
                    </button>
                </>
            )}

            <div className={styles.divider} />

            {/* View Option Chain */}
            <button
                className={styles.contextMenuItem}
                onClick={() => {
                    onOpenOptionChain?.(symbol, exchange);
                    onClose();
                }}
            >
                <span className={styles.menuIcon}></span>
                <span className={styles.menuLabel}>View Option Chain</span>
            </button>

            {/* Settings */}
            <button
                className={styles.contextMenuItem}
                onClick={() => {
                    onOpenSettings?.();
                    onClose();
                }}
            >
                <span className={styles.menuIcon}><SettingsIcon /></span>
                <span className={styles.menuLabel}>Settings...</span>
            </button>
        </div>
    );
};

export default ChartContextMenu;
