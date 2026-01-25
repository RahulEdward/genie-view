"""
Check available expiries in the database
"""

import asyncio
import sys

sys.path.insert(0, ".")

from app.db.session import async_session_maker
from app.models.database import InstrumentMaster
from sqlalchemy import select, func


async def check_expiries():
    """Check available expiries for NIFTY options"""
    async with async_session_maker() as db:
        # Get unique expiries for NIFTY options
        result = await db.execute(
            select(
                InstrumentMaster.expiry,
                func.count(InstrumentMaster.id).label('count')
            ).where(
                InstrumentMaster.name == "NIFTY",
                InstrumentMaster.exchange == "NFO",
                InstrumentMaster.option_type.in_(["CE", "PE"])
            ).group_by(
                InstrumentMaster.expiry
            ).order_by(
                InstrumentMaster.expiry
            )
        )
        
        expiries = result.all()
        
        print(f"\nFound {len(expiries)} expiries for NIFTY options on NFO:")
        print("="*60)
        
        for expiry, count in expiries[:10]:  # Show first 10
            print(f"  {expiry}: {count} options")
        
        if len(expiries) > 10:
            print(f"  ... and {len(expiries) - 10} more expiries")
        
        # Also check sample instruments
        print("\n" + "="*60)
        print("Sample NIFTY option instruments:")
        print("="*60)
        
        result = await db.execute(
            select(InstrumentMaster).where(
                InstrumentMaster.name == "NIFTY",
                InstrumentMaster.exchange == "NFO",
                InstrumentMaster.option_type.in_(["CE", "PE"])
            ).limit(5)
        )
        
        instruments = result.scalars().all()
        
        for inst in instruments:
            print(f"  Symbol: {inst.symbol}")
            print(f"    Name: {inst.name}")
            print(f"    Expiry: {inst.expiry}")
            print(f"    Strike: {inst.strike}")
            print(f"    Type: {inst.option_type}")
            print()


if __name__ == "__main__":
    asyncio.run(check_expiries())
