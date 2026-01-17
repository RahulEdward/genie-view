import React, { useState, useEffect } from 'react';
import { Eye, EyeOff, Trash2 } from 'lucide-react';

// Use relative URLs to leverage Vite proxy
const API_BASE = '/api/v1';

const BrokerLogin = ({ onLoginSuccess, onClose }) => {
    const [broker, setBroker] = useState('angelone');
    const [clientId, setClientId] = useState('');
    const [password, setPassword] = useState('');
    const [totp, setTotp] = useState('');
    const [apiKey, setApiKey] = useState('');
    const [totpSecret, setTotpSecret] = useState('');
    const [saveCredentials, setSaveCredentials] = useState(false);
    
    const [showPassword, setShowPassword] = useState(false);
    const [showApiKey, setShowApiKey] = useState(false);
    const [showTotpSecret, setShowTotpSecret] = useState(false);
    
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [savedAccounts, setSavedAccounts] = useState([]);
    const [selectedSavedAccount, setSelectedSavedAccount] = useState(null);
    const [isQuickLogin, setIsQuickLogin] = useState(false);

    // Fetch saved accounts on mount
    useEffect(() => {
        fetchSavedAccounts();
    }, []);

    // Auto-select if only one saved account exists
    useEffect(() => {
        if (savedAccounts.length === 1 && !selectedSavedAccount) {
            handleSelectAccount(savedAccounts[0]);
        }
    }, [savedAccounts]);

    const fetchSavedAccounts = async () => {
        try {
            const response = await fetch(`${API_BASE}/auth/credentials`);
            if (response.ok) {
                const data = await response.json();
                setSavedAccounts(data.data || []);
            }
        } catch (err) {
            console.error('Failed to fetch saved accounts:', err);
        }
    };

    const handleDeleteAccount = async (broker, clientId) => {
        try {
            const response = await fetch(
                `${API_BASE}/auth/credentials/${broker}/${clientId}`,
                { method: 'DELETE' }
            );
            if (response.ok) {
                fetchSavedAccounts();
                // Reset if deleted account was selected
                if (selectedSavedAccount?.client_id === clientId) {
                    setSelectedSavedAccount(null);
                    setIsQuickLogin(false);
                    setClientId('');
                }
            }
        } catch (err) {
            console.error('Failed to delete account:', err);
        }
    };

    const handleSelectAccount = (account) => {
        setSelectedSavedAccount(account);
        setIsQuickLogin(true);
        setBroker(account.broker);
        setClientId(account.client_id);
        // Clear fields not needed for quick login
        setPassword('');
        setApiKey('');
        setTotpSecret('');
        setTotp('');
        setError('');
    };

    const handleNewLogin = () => {
        setSelectedSavedAccount(null);
        setIsQuickLogin(false);
        setClientId('');
        setPassword('');
        setApiKey('');
        setTotp('');
        setError('');
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        
        if (isQuickLogin) {
            // Quick login - only TOTP required
            if (!totp.trim()) {
                setError('Please enter TOTP code');
                return;
            }
        } else {
            // Full login - all fields required
            if (!clientId.trim() || !password.trim() || !totp.trim() || !apiKey.trim()) {
                setError('Please fill in all required fields');
                return;
            }
        }

        setIsLoading(true);
        setError('');

        try {
            let response;
            
            if (isQuickLogin && selectedSavedAccount) {
                // Quick login with saved credentials
                response = await fetch(`${API_BASE}/auth/quick-login?broker=${encodeURIComponent(broker)}&client_id=${encodeURIComponent(clientId)}&totp=${encodeURIComponent(totp)}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
            } else {
                // Full login
                response = await fetch(`${API_BASE}/auth/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        broker,
                        client_id: clientId,
                        password,
                        totp,
                        api_key: apiKey,
                        totp_secret: totpSecret || null,
                        save_credentials: saveCredentials
                    })
                });
            }

            const data = await response.json();

            if (response.ok && data.status === 'success') {
                // Save API key to localStorage for frontend use
                localStorage.setItem('aa_apikey', data.data.apikey);
                localStorage.setItem('aa_broker', data.data.broker);
                localStorage.setItem('aa_client_id', data.data.client_id);
                
                onLoginSuccess(data.data.apikey);
            } else {
                setError(data.detail?.message || data.message || 'Login failed');
            }
        } catch (err) {
            console.error('Login error:', err);
            setError('Could not connect to server. Please check if backend is running.');
        } finally {
            setIsLoading(false);
        }
    };

    const inputStyle = {
        width: '100%',
        padding: '12px',
        backgroundColor: '#131722',
        border: '1px solid #363a45',
        borderRadius: '4px',
        color: '#d1d4dc',
        fontSize: '14px',
        outline: 'none',
        boxSizing: 'border-box'
    };

    const labelStyle = {
        display: 'block',
        color: '#d1d4dc',
        fontSize: '13px',
        marginBottom: '6px',
        fontWeight: 500
    };

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.85)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 10000
        }}>
            <div style={{
                backgroundColor: '#1e222d',
                borderRadius: '8px',
                padding: '24px',
                width: '440px',
                maxWidth: '95%',
                maxHeight: '90vh',
                overflowY: 'auto',
                boxShadow: '0 4px 24px rgba(0, 0, 0, 0.5)'
            }}>
                <h2 style={{
                    margin: '0 0 8px 0',
                    color: '#d1d4dc',
                    fontSize: '20px',
                    fontWeight: 600
                }}>
                    Broker Login
                </h2>
                <p style={{
                    margin: '0 0 20px 0',
                    color: '#787b86',
                    fontSize: '13px'
                }}>
                    Connect to your broker account
                </p>

                {/* Saved Accounts */}
                {savedAccounts.length > 0 && (
                    <div style={{ marginBottom: '20px' }}>
                        <label style={labelStyle}>Saved Accounts</label>
                        <div style={{
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '8px'
                        }}>
                            {savedAccounts.map((acc, idx) => (
                                <div key={idx} style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    padding: '10px 12px',
                                    backgroundColor: '#131722',
                                    borderRadius: '4px',
                                    border: clientId === acc.client_id ? '1px solid #2962ff' : '1px solid #363a45',
                                    cursor: 'pointer'
                                }}
                                onClick={() => handleSelectAccount(acc)}
                                >
                                    <div>
                                        <span style={{ color: '#d1d4dc', fontSize: '14px' }}>
                                            {acc.client_id}
                                        </span>
                                        <span style={{ color: '#787b86', fontSize: '12px', marginLeft: '8px' }}>
                                            ({acc.broker})
                                        </span>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleDeleteAccount(acc.broker, acc.client_id);
                                        }}
                                        style={{
                                            background: 'none',
                                            border: 'none',
                                            color: '#787b86',
                                            cursor: 'pointer',
                                            padding: '4px'
                                        }}
                                    >
                                        <Trash2 size={16} />
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                <form onSubmit={handleSubmit}>
                    {/* Quick Login Mode - Only show TOTP */}
                    {isQuickLogin && selectedSavedAccount ? (
                        <>
                            <div style={{
                                padding: '16px',
                                backgroundColor: '#131722',
                                borderRadius: '4px',
                                marginBottom: '16px',
                                border: '1px solid #2962ff'
                            }}>
                                <div style={{ color: '#787b86', fontSize: '12px', marginBottom: '4px' }}>
                                    Quick Login as
                                </div>
                                <div style={{ color: '#d1d4dc', fontSize: '16px', fontWeight: 500 }}>
                                    {selectedSavedAccount.client_id}
                                    <span style={{ color: '#787b86', fontSize: '13px', marginLeft: '8px' }}>
                                        ({selectedSavedAccount.broker})
                                    </span>
                                </div>
                            </div>

                            {/* TOTP */}
                            <div style={{ marginBottom: '14px' }}>
                                <label style={labelStyle}>TOTP Code *</label>
                                <input
                                    type="text"
                                    value={totp}
                                    onChange={(e) => setTotp(e.target.value)}
                                    placeholder="Enter 6-digit TOTP code"
                                    maxLength={6}
                                    style={inputStyle}
                                    autoFocus
                                />
                            </div>

                            {/* Switch to full login */}
                            <div style={{ marginBottom: '16px', textAlign: 'center' }}>
                                <button
                                    type="button"
                                    onClick={handleNewLogin}
                                    style={{
                                        background: 'none',
                                        border: 'none',
                                        color: '#2962ff',
                                        fontSize: '13px',
                                        cursor: 'pointer',
                                        textDecoration: 'underline'
                                    }}
                                >
                                    Login with different account
                                </button>
                            </div>
                        </>
                    ) : (
                        <>
                            {/* Broker Select */}
                            <div style={{ marginBottom: '14px' }}>
                                <label style={labelStyle}>Broker</label>
                                <select
                                    value={broker}
                                    onChange={(e) => setBroker(e.target.value)}
                                    style={{ ...inputStyle, cursor: 'pointer' }}
                                >
                                    <option value="angelone">Angel One</option>
                                </select>
                            </div>

                            {/* Client ID */}
                            <div style={{ marginBottom: '14px' }}>
                                <label style={labelStyle}>Client ID *</label>
                                <input
                                    type="text"
                                    value={clientId}
                                    onChange={(e) => setClientId(e.target.value)}
                                    placeholder="Enter your client ID"
                                    style={inputStyle}
                                />
                            </div>

                            {/* API Key */}
                            <div style={{ marginBottom: '14px' }}>
                                <label style={labelStyle}>API Key *</label>
                                <div style={{ position: 'relative' }}>
                                    <input
                                        type={showApiKey ? 'text' : 'password'}
                                        value={apiKey}
                                        onChange={(e) => setApiKey(e.target.value)}
                                        placeholder="Enter your broker API key"
                                        style={{ ...inputStyle, paddingRight: '40px' }}
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowApiKey(!showApiKey)}
                                        style={{
                                            position: 'absolute',
                                            right: '8px',
                                            top: '50%',
                                            transform: 'translateY(-50%)',
                                            background: 'none',
                                            border: 'none',
                                            color: '#787b86',
                                            cursor: 'pointer'
                                        }}
                                    >
                                        {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                                    </button>
                                </div>
                            </div>

                            {/* Password */}
                            <div style={{ marginBottom: '14px' }}>
                                <label style={labelStyle}>Password/PIN *</label>
                                <div style={{ position: 'relative' }}>
                                    <input
                                        type={showPassword ? 'text' : 'password'}
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        placeholder="Enter your password or PIN"
                                        style={{ ...inputStyle, paddingRight: '40px' }}
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPassword(!showPassword)}
                                        style={{
                                            position: 'absolute',
                                            right: '8px',
                                            top: '50%',
                                            transform: 'translateY(-50%)',
                                            background: 'none',
                                            border: 'none',
                                            color: '#787b86',
                                            cursor: 'pointer'
                                        }}
                                    >
                                        {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                                    </button>
                                </div>
                            </div>

                            {/* TOTP */}
                            <div style={{ marginBottom: '14px' }}>
                                <label style={labelStyle}>TOTP Code *</label>
                                <input
                                    type="text"
                                    value={totp}
                                    onChange={(e) => setTotp(e.target.value)}
                                    placeholder="Enter 6-digit TOTP code"
                                    maxLength={6}
                                    style={inputStyle}
                                />
                            </div>

                            {/* TOTP Secret (Optional) */}
                            <div style={{ marginBottom: '14px' }}>
                                <label style={labelStyle}>
                                    TOTP Secret 
                                    <span style={{ color: '#787b86', fontWeight: 400 }}> (optional, for auto-TOTP)</span>
                                </label>
                                <div style={{ position: 'relative' }}>
                                    <input
                                        type={showTotpSecret ? 'text' : 'password'}
                                        value={totpSecret}
                                        onChange={(e) => setTotpSecret(e.target.value)}
                                        placeholder="Enter TOTP secret key"
                                        style={{ ...inputStyle, paddingRight: '40px' }}
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowTotpSecret(!showTotpSecret)}
                                        style={{
                                            position: 'absolute',
                                            right: '8px',
                                            top: '50%',
                                            transform: 'translateY(-50%)',
                                            background: 'none',
                                            border: 'none',
                                            color: '#787b86',
                                            cursor: 'pointer'
                                        }}
                                    >
                                        {showTotpSecret ? <EyeOff size={16} /> : <Eye size={16} />}
                                    </button>
                                </div>
                            </div>

                            {/* Save Credentials Checkbox */}
                            <div style={{ marginBottom: '20px' }}>
                                <label style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px',
                                    cursor: 'pointer',
                                    color: '#d1d4dc',
                                    fontSize: '13px'
                                }}>
                                    <input
                                        type="checkbox"
                                        checked={saveCredentials}
                                        onChange={(e) => setSaveCredentials(e.target.checked)}
                                        style={{ cursor: 'pointer' }}
                                    />
                                    Save credentials for quick login
                                </label>
                            </div>
                        </>
                    )}

                    {/* Error Message */}
                    {error && (
                        <div style={{
                            padding: '10px 12px',
                            backgroundColor: 'rgba(242, 54, 69, 0.1)',
                            border: '1px solid #f23645',
                            borderRadius: '4px',
                            color: '#f23645',
                            fontSize: '13px',
                            marginBottom: '16px'
                        }}>
                            {error}
                        </div>
                    )}

                    {/* Submit Button */}
                    <button
                        type="submit"
                        disabled={isLoading}
                        style={{
                            width: '100%',
                            padding: '12px',
                            backgroundColor: isLoading ? '#4a5568' : '#2962ff',
                            border: 'none',
                            borderRadius: '4px',
                            color: '#fff',
                            fontSize: '14px',
                            fontWeight: 500,
                            cursor: isLoading ? 'not-allowed' : 'pointer',
                            opacity: isLoading ? 0.7 : 1
                        }}
                    >
                        {isLoading ? 'Connecting...' : 'Login'}
                    </button>
                </form>
            </div>
        </div>
    );
};

export default BrokerLogin;
