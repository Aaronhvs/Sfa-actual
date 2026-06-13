"""Analyze progressive_passes and progressive_carries distribution by position."""
import asyncio
import sys
sys.path.insert(0, "/code/src")

from sqlalchemy import text
from sfa.infrastructure.database import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as session:

        # 1. Average stats per fixture by position group (MF, FW, DF)
        r = await session.execute(text("""
            SELECT
                p.position,
                COUNT(*) as fixtures,
                ROUND(AVG(ps.progressive_passes), 2) as avg_prog_passes,
                ROUND(AVG(ps.progressive_carries), 2) as avg_prog_carries,
                ROUND(AVG(ps.passes_key), 2) as avg_key_passes,
                ROUND(AVG(ps.duels_won), 2) as avg_duels_won,
                ROUND(AVG(ps.dribbles_won), 2) as avg_dribbles_won
            FROM player_stats ps
            JOIN players p ON p.id = ps.player_id
            WHERE ps.progressive_passes > 0 OR ps.progressive_carries > 0
            GROUP BY p.position
            ORDER BY p.position
        """))
        print("=== Avg stats per fixture by position (rows with prog data) ===")
        for row in r.fetchall():
            print(f"  pos={row[0]:4s} fixtures={row[1]:5d} "
                  f"prog_p={row[2]:5.2f} prog_c={row[3]:5.2f} "
                  f"key_p={row[4]:5.2f} duels={row[5]:5.2f} dribs={row[6]:5.2f}")

        # 2. Top 15 MF by avg progressive_passes per fixture
        r = await session.execute(text("""
            SELECT
                p.name,
                c.name as comp,
                COUNT(*) as fixtures,
                ROUND(AVG(ps.progressive_passes), 2) as avg_prog_p,
                ROUND(AVG(ps.progressive_carries), 2) as avg_prog_c,
                ROUND(AVG(ps.passes_key), 2) as avg_key_p
            FROM player_stats ps
            JOIN players p ON p.id = ps.player_id
            JOIN fixtures f ON f.id = ps.fixture_id
            JOIN competitions c ON c.id = f.competition_id
            WHERE p.position IN ('MC', 'MCO', 'MCD', 'MO', 'MI', 'MD')
              AND f.season = '2024'
              AND ps.progressive_passes > 0
            GROUP BY p.name, c.name
            HAVING COUNT(*) >= 10
            ORDER BY avg_prog_p DESC
            LIMIT 15
        """))
        print("\n=== Top 15 MF by avg progressive_passes (min 10 fixtures) ===")
        for row in r.fetchall():
            print(f"  {row[0]:25s} ({row[2]:2d} fix) prog_p={row[3]:5.2f} prog_c={row[4]:5.2f} key_p={row[5]:5.2f}")

        # 3. Top 15 FW by avg progressive_carries
        r = await session.execute(text("""
            SELECT
                p.name,
                c.name as comp,
                COUNT(*) as fixtures,
                ROUND(AVG(ps.progressive_passes), 2) as avg_prog_p,
                ROUND(AVG(ps.progressive_carries), 2) as avg_prog_c,
                ROUND(AVG(ps.passes_key), 2) as avg_key_p
            FROM player_stats ps
            JOIN players p ON p.id = ps.player_id
            JOIN fixtures f ON f.id = ps.fixture_id
            JOIN competitions c ON c.id = f.competition_id
            WHERE p.position IN ('DEL', 'EI', 'ED', 'DC', 'SD')
              AND f.season = '2024'
              AND ps.progressive_carries > 0
            GROUP BY p.name, c.name
            HAVING COUNT(*) >= 10
            ORDER BY avg_prog_c DESC
            LIMIT 15
        """))
        print("\n=== Top 15 FW by avg progressive_carries (min 10 fixtures) ===")
        for row in r.fetchall():
            print(f"  {row[0]:25s} ({row[2]:2d} fix) prog_c={row[4]:5.2f} prog_p={row[3]:5.2f} key_p={row[5]:5.2f}")

        # 4. Coverage: how many fixtures have prog data vs total
        r = await session.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN progressive_passes > 0 THEN 1 ELSE 0 END) as has_prog_p,
                SUM(CASE WHEN progressive_carries > 0 THEN 1 ELSE 0 END) as has_prog_c
            FROM player_stats
        """))
        row = r.fetchone()
        print(f"\n=== Coverage ===")
        print(f"  Total rows: {row[0]}")
        print(f"  Has prog_passes > 0: {row[1]} ({row[1]/row[0]*100:.1f}%)")
        print(f"  Has prog_carries > 0: {row[2]} ({row[2]/row[0]*100:.1f}%)")

        # 5. Pedri specifically
        r = await session.execute(text("""
            SELECT
                ps.progressive_passes,
                ps.progressive_carries,
                ps.passes_key,
                ps.duels_won,
                ps.dribbles_won,
                f.season
            FROM player_stats ps
            JOIN players p ON p.id = ps.player_id
            JOIN fixtures f ON f.id = ps.fixture_id
            WHERE p.name ILIKE '%pedri%' AND f.season = '2024'
            ORDER BY ps.progressive_passes DESC
            LIMIT 10
        """))
        rows = r.fetchall()
        print(f"\n=== Pedri 2024 - progressive stats per fixture ===")
        for row in rows:
            print(f"  prog_p={row[0]:3d} prog_c={row[1]:3d} key_p={row[2]:3d} duels={row[3]:3d} dribs={row[4]:3d}")


asyncio.run(main())
