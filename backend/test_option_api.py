#!/usr/bin/env python
"""Test option chain API"""
import requests
import json

url = "http://127.0.0.1:8000/api/v1/optionchain"
payload = {
    "symbol": "NIFTY",
    "exchange": "NFO",
    "expiry": "27JAN2026"
}

print(f"Testing: POST {url}")
print(f"Payload: {json.dumps(payload)}")

try:
    response = requests.post(url, json=payload, timeout=30)
    print(f"Status: {response.status_code}")
    
    data = response.json()
    print(f"\nResponse:")
    print(f"  spot_price: {data.get('spot_price')}")
    print(f"  expiry: {data.get('expiry')}")
    print(f"  calls count: {len(data.get('calls', []))}")
    print(f"  puts count: {len(data.get('puts', []))}")
    
    if data.get('calls'):
        print(f"\nSample calls:")
        for call in data['calls'][:3]:
            print(f"  Strike {call.get('strike')}: LTP={call.get('ltp')}, OI={call.get('oi')}")
    
    if data.get('puts'):
        print(f"\nSample puts:")
        for put in data['puts'][:3]:
            print(f"  Strike {put.get('strike')}: LTP={put.get('ltp')}, OI={put.get('oi')}")
            
except Exception as e:
    print(f"Error: {e}")
