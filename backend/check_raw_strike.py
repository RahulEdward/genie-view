import httpx
import json

url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

print("Downloading instrument master...")
response = httpx.get(url, timeout=60.0)
data = response.json()

# Find NIFTY options
nifty_options = [d for d in data if d.get("name") == "NIFTY" and d.get("symbol", "").endswith(("CE", "PE"))][:5]

print(f"\nSample NIFTY options from API:")
for opt in nifty_options:
    print(f"  Symbol: {opt.get('symbol')}, Strike: {opt.get('strike')}, Expiry: {opt.get('expiry')}")
