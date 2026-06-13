"""Quick check of xa coverage per competition via SQLAlchemy."""
import asyncio
import sys
sys.path.insert(0, "/code/src")

from sqlalchemy import text
from sfa.infrastructure.database import AsyncSessionLocal

QUERY = """
SELECT c.name, COUNT(DISTINCT ps.player_id) as players_with_xa
FROM player_stats ps
JOIN fixtures f ON f.id = ps.fixture_id
JOIN competitions c ON c.id = f.competition_id
WHERE ps.xa > 0
GROUP BY c.name
ORDER BY c.name
"""

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(QUERY))
        rows = result.fetchall()
        if not rows:
            print("NO XA DATA FOUND")
        else:
            print(f"{'Competition':<25} {'Players with xa':>15}")
            print("-" * 42)
            for name, count in rows:
                print(f"{name:<25} {count:>15}")

asyncio.run(main())
