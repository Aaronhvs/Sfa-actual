"""Test if update_player_stats_from_fbref actually writes xa."""
import asyncio
import sys
sys.path.insert(0, "/code/src")

from sqlalchemy import text
from sfa.infrastructure.database import AsyncSessionLocal
from sfa.infrastructure.repositories.enrichment_repository import EnrichmentRepository

PEDRI_ID = 40  # from ranking data

async def main():
    async with AsyncSessionLocal() as session:
        repo = EnrichmentRepository(session)

        # Check before
        r = await session.execute(text(
            "SELECT player_id, fixture_id, xa FROM player_stats WHERE player_id = :pid LIMIT 3"
        ), {"pid": PEDRI_ID})
        rows = r.fetchall()
        print(f"Before update - Pedri rows:")
        for row in rows:
            print(f"  player_id={row[0]} fixture_id={row[1]} xa={row[2]}")

        # Write xa = 7.23 for Pedri (season 2024)
        await repo.update_player_stats_from_fbref(PEDRI_ID, "2024", {"xa": 7.23})
        await session.flush()

        # Check after
        r = await session.execute(text(
            "SELECT player_id, fixture_id, xa FROM player_stats WHERE player_id = :pid LIMIT 3"
        ), {"pid": PEDRI_ID})
        rows = r.fetchall()
        print(f"\nAfter update (before commit) - Pedri rows:")
        for row in rows:
            print(f"  player_id={row[0]} fixture_id={row[1]} xa={row[2]}")

        # COMMIT
        await session.commit()
        print("\nCommitted!")

    # Read back after commit
    async with AsyncSessionLocal() as session:
        r = await session.execute(text(
            "SELECT player_id, fixture_id, xa FROM player_stats WHERE player_id = :pid LIMIT 3"
        ), {"pid": PEDRI_ID})
        rows = r.fetchall()
        print(f"\nAfter commit - Pedri rows:")
        for row in rows:
            print(f"  player_id={row[0]} fixture_id={row[1]} xa={row[2]}")

asyncio.run(main())
