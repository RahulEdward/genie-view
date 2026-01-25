/**
 * Option Chain API Test Script
 * 
 * Run this in browser console to test option chain functionality
 * 
 * Usage:
 * 1. Open browser console (F12)
 * 2. Copy and paste this entire script
 * 3. Run: testOptionChain('NIFTY', 'NFO')
 */

// Get API key from localStorage
function getApiKey() {
    return localStorage.getItem('aa_apikey') || '';
}

// Get API base URL
function getApiBase() {
    return '/api/v1';  // Use Vite proxy
}

// Test option chain API
async function testOptionChain(underlying = 'NIFTY', exchange = 'NFO', strikeCount = 10) {
    console.log('='.repeat(60));
    console.log('OPTION CHAIN API TEST');
    console.log('='.repeat(60));
    
    const apiKey = getApiKey();
    
    if (!apiKey) {
        console.error('❌ No API key found. Please login first.');
        return;
    }
    
    console.log('✓ API Key:', apiKey.substring(0, 10) + '...');
    console.log('✓ Underlying:', underlying);
    console.log('✓ Exchange:', exchange);
    console.log('✓ Strike Count:', strikeCount);
    console.log('-'.repeat(60));
    
    try {
        const requestBody = {
            apikey: apiKey,
            underlying: underlying,
            exchange: exchange,
            strike_count: strikeCount
        };
        
        console.log('📤 Request Body:', JSON.stringify(requestBody, null, 2));
        console.log('-'.repeat(60));
        
        const url = `${getApiBase()}/optionchain`;
        console.log('📡 Calling:', url);
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify(requestBody)
        });
        
        console.log('📥 Response Status:', response.status, response.statusText);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('❌ Error Response:', errorText);
            return;
        }
        
        const data = await response.json();
        console.log('✅ Response Data:', data);
        console.log('-'.repeat(60));
        
        if (data && data.status === 'success' && data.data) {
            console.log('✓ Status:', data.status);
            console.log('✓ Underlying:', data.data.underlying);
            console.log('✓ Underlying LTP:', data.data.underlyingLTP);
            console.log('✓ ATM Strike:', data.data.atmStrike);
            console.log('✓ Expiry Date:', data.data.expiryDate);
            console.log('✓ Chain Length:', data.data.chain?.length || 0);
            console.log('-'.repeat(60));
            
            if (data.data.chain && data.data.chain.length > 0) {
                console.log('📊 Sample Strikes (first 3):');
                data.data.chain.slice(0, 3).forEach((strike, idx) => {
                    console.log(`\nStrike ${idx + 1}: ${strike.strike}`);
                    if (strike.ce) {
                        console.log('  CE:', {
                            symbol: strike.ce.symbol,
                            ltp: strike.ce.ltp,
                            oi: strike.ce.oi,
                            label: strike.ce.label
                        });
                    }
                    if (strike.pe) {
                        console.log('  PE:', {
                            symbol: strike.pe.symbol,
                            ltp: strike.pe.ltp,
                            oi: strike.pe.oi,
                            label: strike.pe.label
                        });
                    }
                });
            }
            
            console.log('='.repeat(60));
            console.log('✅ TEST PASSED - Option chain data received successfully!');
            console.log('='.repeat(60));
            
            return data.data;
        } else {
            console.error('❌ Invalid response format:', data);
        }
        
    } catch (error) {
        console.error('❌ Test Failed:', error);
        console.error('Error details:', error.message);
    }
}

// Test with different underlyings
async function testMultipleUnderlyings() {
    console.log('\n🔄 Testing multiple underlyings...\n');
    
    const underlyings = [
        { symbol: 'NIFTY', exchange: 'NFO' },
        { symbol: 'BANKNIFTY', exchange: 'NFO' },
        { symbol: 'FINNIFTY', exchange: 'NFO' }
    ];
    
    for (const { symbol, exchange } of underlyings) {
        await testOptionChain(symbol, exchange, 5);
        await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1 second between calls
    }
}

// Export functions to window for console access
window.testOptionChain = testOptionChain;
window.testMultipleUnderlyings = testMultipleUnderlyings;

console.log('✅ Option Chain Test Script Loaded!');
console.log('');
console.log('Available commands:');
console.log('  testOptionChain(underlying, exchange, strikeCount)');
console.log('  testMultipleUnderlyings()');
console.log('');
console.log('Examples:');
console.log('  testOptionChain("NIFTY", "NFO", 10)');
console.log('  testOptionChain("BANKNIFTY", "NFO", 15)');
console.log('  testMultipleUnderlyings()');
console.log('');
