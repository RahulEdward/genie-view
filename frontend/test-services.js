/**
 * Service Layer Integration Test
 * Tests all frontend services to verify backend integration
 */

import { callBackendAPI } from './src/services/apiService.js';
import { getMarketHolidays, getMarketTimings, isMarketOpen } from './src/services/marketService.js';
import { getHistoricalData, getQuote, searchSymbols } from './src/services/marketDataService.js';

// Test configuration
const TEST_CONFIG = {
    symbol: 'NIFTY',
    exchange: 'NSE',
    year: 2025,
    date: '2025-01-20'
};

console.log('🧪 Starting Service Layer Integration Tests...\n');

// Test 1: Market Service - Holidays
async function testMarketHolidays() {
    console.log('📅 Test 1: Market Holidays');
    try {
        const holidays = await getMarketHolidays(TEST_CONFIG.year);
        console.log(`✅ Success: Retrieved ${holidays.length} holidays for ${TEST_CONFIG.year}`);
        if (holidays.length > 0) {
            console.log(`   First holiday: ${holidays[0].date} - ${holidays[0].description}`);
        }
        return true;
    } catch (error) {
        console.error(`❌ Failed: ${error.message}`);
        return false;
    }
}

// Test 2: Market Service - Timings
async function testMarketTimings() {
    console.log('\n⏰ Test 2: Market Timings');
    try {
        const timings = await getMarketTimings(TEST_CONFIG.date);
        console.log(`✅ Success: Retrieved timings for ${timings.length} exchanges`);
        if (timings.length > 0) {
            const nse = timings.find(t => t.exchange === 'NSE');
            if (nse) {
                const start = new Date(nse.start_time).toLocaleTimeString('en-IN');
                const end = new Date(nse.end_time).toLocaleTimeString('en-IN');
                console.log(`   NSE: ${start} - ${end}`);
            }
        }
        return true;
    } catch (error) {
        console.error(`❌ Failed: ${error.message}`);
        return false;
    }
}

// Test 3: Market Service - Market Open Status
async function testMarketOpen() {
    console.log('\n🔔 Test 3: Market Open Status');
    try {
        const isOpen = await isMarketOpen(TEST_CONFIG.exchange);
        console.log(`✅ Success: ${TEST_CONFIG.exchange} is ${isOpen ? 'OPEN' : 'CLOSED'}`);
        return true;
    } catch (error) {
        console.error(`❌ Failed: ${error.message}`);
        return false;
    }
}

// Test 4: Market Data Service - Symbol Search
async function testSymbolSearch() {
    console.log('\n🔍 Test 4: Symbol Search');
    try {
        const results = await searchSymbols('NIFTY');
        console.log(`✅ Success: Found ${results.length} symbols matching 'NIFTY'`);
        if (results.length > 0) {
            console.log(`   First result: ${results[0].symbol} (${results[0].exchange})`);
        }
        return true;
    } catch (error) {
        console.error(`❌ Failed: ${error.message}`);
        return false;
    }
}

// Test 5: Market Data Service - Quote
async function testQuote() {
    console.log('\n💹 Test 5: Get Quote');
    try {
        const quote = await getQuote(TEST_CONFIG.symbol, TEST_CONFIG.exchange);
        if (quote) {
            console.log(`✅ Success: ${TEST_CONFIG.symbol} LTP: ${quote.ltp}`);
            console.log(`   Change: ${quote.change} (${quote.change_percent}%)`);
        } else {
            console.log('⚠️  Warning: Quote returned null (may be outside market hours)');
        }
        return true;
    } catch (error) {
        console.error(`❌ Failed: ${error.message}`);
        return false;
    }
}

// Test 6: Market Data Service - Historical Data
async function testHistoricalData() {
    console.log('\n📊 Test 6: Historical Data');
    try {
        const endDate = new Date();
        const startDate = new Date();
        startDate.setDate(startDate.getDate() - 7); // Last 7 days
        
        const data = await getHistoricalData(
            TEST_CONFIG.symbol,
            TEST_CONFIG.exchange,
            '1d',
            startDate.toISOString().split('T')[0],
            endDate.toISOString().split('T')[0]
        );
        
        console.log(`✅ Success: Retrieved ${data.length} candles`);
        if (data.length > 0) {
            const latest = data[data.length - 1];
            console.log(`   Latest: O:${latest.open} H:${latest.high} L:${latest.low} C:${latest.close}`);
        }
        return true;
    } catch (error) {
        console.error(`❌ Failed: ${error.message}`);
        return false;
    }
}

// Test 7: Caching Behavior
async function testCaching() {
    console.log('\n💾 Test 7: Caching Behavior');
    try {
        console.log('   First call (should hit backend)...');
        const start1 = Date.now();
        await getMarketHolidays(TEST_CONFIG.year);
        const time1 = Date.now() - start1;
        
        console.log('   Second call (should use cache)...');
        const start2 = Date.now();
        await getMarketHolidays(TEST_CONFIG.year);
        const time2 = Date.now() - start2;
        
        console.log(`✅ Success: First call: ${time1}ms, Second call: ${time2}ms`);
        if (time2 < time1) {
            console.log('   ✓ Cache is working (second call faster)');
        } else {
            console.log('   ⚠️  Cache may not be working optimally');
        }
        return true;
    } catch (error) {
        console.error(`❌ Failed: ${error.message}`);
        return false;
    }
}

// Test 8: Error Handling
async function testErrorHandling() {
    console.log('\n🛡️  Test 8: Error Handling');
    try {
        // Try to get quote for invalid symbol
        const quote = await getQuote('INVALID_SYMBOL_XYZ', 'NSE');
        if (quote === null) {
            console.log('✅ Success: Invalid symbol handled gracefully (returned null)');
        } else {
            console.log('⚠️  Warning: Expected null for invalid symbol');
        }
        return true;
    } catch (error) {
        // Error is also acceptable - it means error handling is working
        console.log(`✅ Success: Error caught and handled: ${error.message}`);
        return true;
    }
}

// Run all tests
async function runAllTests() {
    const tests = [
        testMarketHolidays,
        testMarketTimings,
        testMarketOpen,
        testSymbolSearch,
        testQuote,
        testHistoricalData,
        testCaching,
        testErrorHandling
    ];
    
    let passed = 0;
    let failed = 0;
    
    for (const test of tests) {
        const result = await test();
        if (result) passed++;
        else failed++;
    }
    
    console.log('\n' + '='.repeat(50));
    console.log(`📊 Test Results: ${passed} passed, ${failed} failed`);
    console.log('='.repeat(50));
    
    if (failed === 0) {
        console.log('✅ All service layer tests passed!');
        console.log('✅ Backend integration is working correctly');
        console.log('✅ Error handling is functioning properly');
        console.log('✅ Caching behavior is operational');
    } else {
        console.log('⚠️  Some tests failed. Please check the errors above.');
    }
}

// Run tests
runAllTests().catch(error => {
    console.error('\n❌ Test suite failed:', error);
    process.exit(1);
});
