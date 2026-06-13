"""Detailed xa diagnostic."""
import asyncio
import sys
sys.path.insert(0, "/code/src")

from sqlalchemy import text
from sfa.infrastructure.database import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as session:
        # 1. Count of player_stats rows by xa value
        r = await session.execute(text("""
            SELECT
                CASE WHEN xa = 0 THEN 'xa=0' WHEN xa IS NULL THEN 'xa=NULL' ELSE 'xa>0' END as xa_state,
                COUNT(*) as cnt
            FROM player_stats
            GROUP BY 1 ORDER BY 1
        """))
        print("=== player_stats.xa distribution ===")
        for row in r.fetchall():
            print(f"  {row[0]}: {row[1]}")

        # 2. Top 5 players with highest xa_sum from player_stats
        r = await session.execute(text("""
            SELECT p.name, c.name as comp, SUM(ps.xa) as total_xa
            FROM player_stats ps
            JOIN players p ON p.id = ps.player_id
            JOIN fixtures f ON f.id = ps.fixture_id
            JOIN competitions c ON c.id = f.competition_id
            WHERE ps.xa > 0
            GROUP BY p.name, c.name
            ORDER BY total_xa DESC
            LIMIT 5
        """))
        rows = r.fetchall()
        print("\n=== Top players with xa > 0 (by total_xa) ===")
        if rows:
            for name, comp, xa in rows:
                print(f"  {name} ({comp}): xa={xa:.2f}")
        else:
            print("  None found")

        # 3. Check Pedri's xa across all fixtures
        r = await session.execute(text("""
            SELECT ps.xa, f.season, c.name
            FROM player_stats ps
            JOIN fixtures f ON f.id = ps.fixture_id
            JOIN competitions c ON c.id = f.competition_id
            JOIN players p ON p.id = ps.player_id
            WHERE p.name ILIKE '%pedri%'
            ORDER BY ps.xa DESC
            LIMIT 5
        """))
        rows = r.fetchall()
        print("\n=== Pedri xa values ===")
        if rows:
            for xa, season, comp in rows:
                print(f"  season={season} comp={comp} xa={xa}")
        else:
            print("  Player not found")

asyncio.run(main())
