#!/usr/bin/env python
"""Check nearest expiry for NIFTY options"""
import sqlite3
import os
from datetime import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

# Get all NIFTY expiries
cursor.execute("SELECT DISTINCT expiry FROM instrument_master WHERE name = 'NIFTY' AND option_type IS NOT NULL")
expiries = [r[0] for r in cursor.fetchall()]

print(f"Total NIFTY expiries: {len(expiries)}")
print(f"All expiries: {sorted(expiries)}")

# Parse and sort by date
def parse_expiry(exp):
    try:
        return datetime.strptime(exp, "%d%b%Y")
    except:
        return None

parsed = [(e, parse_expiry(e)) for e in expiries if parse_expiry(e)]
parsed.sort(key=lambda x: x[1])

print(f"\nSorted expiries (nearest first):")
for exp, dt in parsed[:10]:
    print(f"  {exp} -> {dt.strftime('%Y-%m-%d')}")

# Check options for nearest expiry
if parsed:
    nearest = parsed[0][0]
    print(f"\nNearest expiry: {nearest}")
    
    cursor.execute(f"SELECT COUNT(*) FROM instrument_master WHERE name = 'NIFTY' AND expiry = '{nearest}' AND option_type = 'CE'")
    ce_count = cursor.fetchone()[0]
    
    cursor.execute(f"SELECT COUNT(*) FROM instrument_master WHERE name = 'NIFTY' AND expiry = '{nearest}' AND option_type = 'PE'")
    pe_count = cursor.fetchone()[0]
    
    print(f"CE options: {ce_count}, PE options: {pe_count}")
    
    # Sample strikes
    cursor.execute(f"SELECT DISTINCT strike FROM instrument_master WHERE name = 'NIFTY' AND expiry = '{nearest}' ORDER BY strike")
    strikes = [r[0] for r in cursor.fetchall()]
    print(f"Strikes: {strikes[:20]}...")

conn.close()
