import sqlite3

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

# Check NIFTY options
cursor.execute("""
    SELECT COUNT(*), expiry 
    FROM instrument_master 
    WHERE name='NIFTY' AND option_type IS NOT NULL 
    GROUP BY expiry 
    ORDER BY expiry 
    LIMIT 10
""")
print('NIFTY options by expiry:')
for r in cursor.fetchall():
    print(r)

# Check sample NIFTY option
cursor.execute("""
    SELECT symbol, name, expiry, strike, option_type, token
    FROM instrument_master 
    WHERE name='NIFTY' AND option_type='CE'
    LIMIT 5
""")
print('\nSample NIFTY CE options:')
for r in cursor.fetchall():
    print(r)

conn.close()
