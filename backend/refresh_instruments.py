"""
Refresh instrument master data with corrected strike prices.
"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.db.session import async_session_maker
from app.services.symbol import SymbolService
from app.brokers.angelone.adapter import AngelOneAdapter

async def main():
    print("Refreshing instrument master data...")
    
    async with async_session_maker() as db:
        broker = AngelOneAdapter(api_key="dummy")
        symbol_service = SymbolService(broker, db)
        
        # Download and store instruments
        raw_instruments = await symbol_service.download_instrument_master()
        print(f"Downloaded {len(raw_instruments)} raw instruments")
        
        # Parse and store
        instruments = []
        for record in raw_instruments:
            inst = symbol_service.parse_instrument_record(record)
            if inst:
                instruments.append(inst)
        
        print(f"Parsed {len(instruments)} valid instruments")
        
        count = await symbol_service.store_instruments_bulk(instruments)
        print(f"Stored {count} instruments")
        
        # Verify NIFTY strikes are correct now
        from sqlalchemy import select
        from app.models.database import InstrumentMaster
        
        result = await db.execute(
            select(InstrumentMaster).where(
                InstrumentMaster.name == "NIFTY",
                InstrumentMaster.option_type == "CE"
            ).limit(5)
        )
        
        print("\nSample NIFTY CE options after fix:")
        for inst in result.scalars():
            print(f"  {inst.symbol}: strike={inst.strike}, expiry={inst.expiry}")

if __name__ == "__main__":
    asyncio.run(main())
