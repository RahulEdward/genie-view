#!/usr/bin/env python
"""Check option chain data in database"""
import sqlite3
import os

# Change to backend directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

# Total instruments
cursor.execute('SELECT COUNT(*) FROM instrument_master')
print(f'Total instruments: {cursor.fetchone()[0]}')

# Options count
cursor.execute('SELECT COUNT(*) FROM instrument_master WHERE option_type IS NOT NULL')
print(f'Total options: {cursor.fetchone()[0]}')

# NIFTY options
cursor.execute("SELECT COUNT(*) FROM instrument_master WHERE name = 'NIFTY' AND option_type IS NOT NULL")
print(f'NIFTY options: {cursor.fetchone()[0]}')

# NIFTY expiries
cursor.execute("SELECT DISTINCT expiry FROM instrument_master WHERE name = 'NIFTY' AND option_type IS NOT NULL ORDER BY expiry LIMIT 10")
print('NIFTY Expiries:', [r[0] for r in cursor.fetchall()])

# Sample NIFTY options
cursor.execute("SELECT symbol, strike, option_type, expiry FROM instrument_master WHERE name = 'NIFTY' AND option_type IS NOT NULL ORDER BY strike LIMIT 10")
print('\nSample NIFTY options:')
for row in cursor.fetchall():
    print(f'  {row[0]} - Strike: {row[1]}, Type: {row[2]}, Expiry: {row[3]}')

conn.close()
