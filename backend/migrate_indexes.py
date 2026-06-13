"""
Migration: add missing indexes for performance.

Run inside the container:
    docker compose -f docker-compose-development.yml exec api python migrate_indexes.py
"""
import asyncio
import logging

from sqlalchemy import text
from sfa.infrastructure.database import engine

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

INDEXES = [
    # player_events: every player-page query filters by player_id
    (
        "idx_player_events_player_id",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_player_events_player_id "
        "ON player_events (player_id)",
    ),
    # player_events: joins from fixture side
    (
        "idx_player_events_fixture_id",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_player_events_fixture_id "
        "ON player_events (fixture_id)",
    ),
    # fixtures: ranking queries filter by season and competition_id
    (
        "idx_fixtures_season_competition",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fixtures_season_competition "
        "ON fixtures (season, competition_id)",
    ),
    # sfa_season_scores: ranking aggregates by season; get_global_rank scans by season
    (
        "idx_sfa_season_scores_season",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sfa_season_scores_season "
        "ON sfa_season_scores (season)",
    ),
    # sfa_season_scores: player detail queries filter by player_id + season
    (
        "idx_sfa_season_scores_player_season",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sfa_season_scores_player_season "
        "ON sfa_season_scores (player_id, season)",
    ),
    # player_stats: season stats aggregation filters by player_id
    (
        "idx_player_stats_player_id",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_player_stats_player_id "
        "ON player_stats (player_id)",
    ),
    # player_stats: backfill queries filter by fixture_id
    (
        "idx_player_stats_fixture_id",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_player_stats_fixture_id "
        "ON player_stats (fixture_id)",
    ),
]


async def run() -> None:
    # CONCURRENTLY cannot run inside a transaction, so use autocommit
    async with engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        for name, ddl in INDEXES:
            log.info("Creating index %s ...", name)
            await conn.execute(text(ddl))
            log.info("  OK")
    log.info("All indexes created.")


if __name__ == "__main__":
    asyncio.run(run())
