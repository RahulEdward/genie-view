"""Check if specific symbols exist in database"""
import asyncio
from app.db.session import async_session_maker
from app.models.database import InstrumentMaster
from sqlalchemy import select

async def main():
    symbols = ['NIFTY27JAN2626950PE', 'NIFTY27JAN2627400PE']
    
    async with async_session_maker() as db:
        result = await db.execute(
            select(InstrumentMaster).where(
                InstrumentMaster.symbol.in_(symbols)
            )
        )
        insts = result.scalars().all()
        
        print(f"Found {len(insts)} instruments out of {len(symbols)} requested")
        for inst in insts:
            print(f"  {inst.symbol}: token={inst.token} (type={type(inst.token).__name__}), strike={inst.strike}, expiry={inst.expiry}")
        
        # Check what symbols DO exist for this expiry
        print("\nChecking all NIFTY 27JAN2026 options with strikes around 26950 and 27400:")
        result = await db.execute(
            select(InstrumentMaster).where(
                InstrumentMaster.name == "NIFTY",
                InstrumentMaster.expiry == "27JAN2026",
                InstrumentMaster.strike.in_([2695000.0, 2740000.0])
            )
        )
        insts = result.scalars().all()
        print(f"Found {len(insts)} instruments")
        for inst in insts:
            print(f"  {inst.symbol}: token={inst.token} (type={type(inst.token).__name__}), strike={inst.strike}")
        
        # Check if any instruments have None tokens
        print("\nChecking for instruments with None tokens:")
        result = await db.execute(
            select(InstrumentMaster).where(
                InstrumentMaster.name == "NIFTY",
                InstrumentMaster.expiry == "27JAN2026",
                InstrumentMaster.token.is_(None)
            )
        )
        none_tokens = result.scalars().all()
        print(f"Found {len(none_tokens)} instruments with None tokens")

if __name__ == "__main__":
    asyncio.run(main())
