"""Regression against an explicitly supplied, populated isolation database.

AGGREGATE_TEST_DATABASE_URL must point at psg_match_recovery_test, never production.
All function changes and row updates are rolled back at the end of each test.
"""
import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

URL = os.environ.get("AGGREGATE_TEST_DATABASE_URL")
pytestmark = [pytest.mark.anyio, pytest.mark.skipif(not URL, reason="Isolated aggregate database URL not supplied")]
MIGRATION = Path(__file__).resolve().parents[2] / "migrations/0059_curated_empty_season_aggregate.sql"


@pytest.mark.parametrize("empty", [True, False])
async def test_bonus_refresh_preserves_protected_aggregate_including_zero_actions(empty):
    assert make_url(URL).database == "psg_match_recovery_test"
    engine = create_async_engine(URL, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            async with connection.begin() as transaction:
                assert await connection.scalar(text("SELECT current_database()")) == "psg_match_recovery_test"
                raw = await connection.get_raw_connection()
                sql = MIGRATION.read_text(encoding="utf-8").strip()
                assert sql.startswith("BEGIN;") and sql.endswith("COMMIT;")
                await raw.driver_connection.execute(sql[6:-7])
                # The migration is repeatable and retains the deployed guard's other protections.
                definition = await connection.scalar(text(
                    "SELECT pg_get_functiondef('validate_curated_season_aggregate()'::regprocedure)"
                ))
                await raw.driver_connection.execute(sql[6:-7])
                assert await connection.scalar(text(
                    "SELECT pg_get_functiondef('validate_curated_season_aggregate()'::regprocedure)"
                )) == definition
                selected = (await connection.execute(text("""
                    SELECT r.id, r.total_pts, r.matches_played, r.achievement_bonus_pts
                    FROM sfa_season_scores r
                    WHERE r.season='2026' AND r.rules_version_id=4
                      AND EXISTS (
                        SELECT 1 FROM player_position_assignments a
                        JOIN position_correction_batches b ON b.batch_id=a.publication_batch_id
                        WHERE a.player_id=r.player_id AND a.season=r.season
                          AND a.status='accepted' AND b.status='published'
                          AND EXISTS (SELECT 1 FROM fixtures f WHERE f.id=ANY(a.applicable_fixture_ids)
                                      AND f.competition_id=r.competition_id)
                      )
                      AND EXISTS (
                        SELECT 1 FROM player_event_scores e WHERE e.player_id=r.player_id
                          AND e.competition_id=r.competition_id AND e.season=r.season
                          AND e.rules_version_id=r.rules_version_id
                      ) = :has_actions
                    ORDER BY r.id LIMIT 1
                """), {"has_actions": not empty})).mappings().one()
                updated = (await connection.execute(text("""
                    UPDATE sfa_season_scores SET achievement_bonus_pts=achievement_bonus_pts
                    WHERE id=:id RETURNING total_pts,matches_played,breakdown,achievement_bonus_pts
                """), {"id": selected["id"]})).mappings().one()
                assert updated["total_pts"] == selected["total_pts"]
                assert updated["matches_played"] == selected["matches_played"]
                assert updated["achievement_bonus_pts"] == selected["achievement_bonus_pts"]
                if empty:
                    assert updated["total_pts"] == 0
                    assert updated["matches_played"] == 0
                    assert updated["breakdown"] == {}
                await transaction.rollback()
    finally:
        await engine.dispose()
