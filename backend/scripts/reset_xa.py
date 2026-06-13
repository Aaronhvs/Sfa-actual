"""Reset Pedri test xa back to 0."""
import asyncio
import sys
sys.path.insert(0, "/code/src")

from sqlalchemy import text
from sfa.infrastructure.database import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as session:
        await session.execute(text(
            "UPDATE player_stats SET xa = 0 WHERE player_id = 40"
        ))
        await session.commit()
    print("Pedri xa reset to 0")

asyncio.run(main())
