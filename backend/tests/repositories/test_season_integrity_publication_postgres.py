"""Opt-in, full-cut rehearsal, exclusively in the restored disposable database."""

import json
import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from sfa.core.dependencies import get_season_integrity_publication_use_cases
from sfa.infrastructure.repositories.season_integrity_publication_repository import (
    TABLES,
    SeasonIntegrityPublicationRepository,
)


async def outside_fingerprints(session, repository):
    result = {}
    for table in TABLES:
        row = (
            await session.execute(
                text(f"""
            SELECT count(*) n,md5(coalesce(string_agg(md5(to_jsonb(t)::text),''
              ORDER BY md5(to_jsonb(t)::text)),'')) hash FROM public.{table} t
            WHERE NOT ({repository._condition(table)})
        """),
                repository._parameters,
            )
        ).one()
        result[table] = (row.n, row.hash)
    return result


@pytest.mark.anyio
async def test_complete_projection_publish_revert_cas_and_transaction_rollback():
    if os.environ.get("INTEGRITY_PUBLICATION_REHEARSAL") != "1":
        pytest.skip("Opt-in full projection rehearsal; requires immutable before/after stages")
    url = os.environ["INTEGRITY_TEST_DATABASE_URL"]
    assert make_url(url).database == "sfa_integrity_2025_test"
    engine = create_async_engine(url, poolclass=NullPool)
    journal = Path(os.environ["INTEGRITY_PUBLICATION_JOURNAL"])
    try:
        async with AsyncSession(engine) as session:
            session.info["position_publication_exclusive"] = True
            repository = SeasonIntegrityPublicationRepository(session)
            await repository.lock()
            before = await repository.validate(False)
            outside_before = await outside_fingerprints(session, repository)
            await session.execute(
                text(
                    "UPDATE player_stats SET goals=goals+1 "
                    "WHERE id=(SELECT min(id) FROM integrity_before_2025.player_stats)"
                )
            )
            with pytest.raises(ValueError, match="CAS"):
                await repository.validate(False)
            await session.rollback()

        async with AsyncSession(engine) as session:
            repository = SeasonIntegrityPublicationRepository(session)
            await repository.lock()
            # GK title bonuses without a scoring rollup are an existing engine exclusion.
            # The identical shape for an outfield player must block publication.
            await session.execute(text("""
                UPDATE integrity_after_2025.player_achievement_bonuses b SET player_id=(
                  SELECT p.id FROM integrity_before_2025.players p WHERE p.position::text<>'GK'
                    AND NOT EXISTS(SELECT 1 FROM integrity_after_2025.sfa_season_scores s
                      WHERE s.player_id=p.id AND s.competition_id=b.competition_id AND s.season=b.season)
                  ORDER BY p.id LIMIT 1)
                WHERE b.id=(SELECT min(x.id) FROM integrity_after_2025.player_achievement_bonuses x
                  JOIN players p ON p.id=x.player_id WHERE p.position::text='GK')
            """))
            with pytest.raises(ValueError, match="achievement aggregate"):
                await repository.validate(False)
            await session.rollback()

        async with AsyncSession(engine) as session:
            promote, _ = get_season_integrity_publication_use_cases(session, journal)
            key, after = await promote.execute()
            assert after.fingerprint != before.fingerprint
            assert await session.scalar(text("SELECT current_setting('sfa.position_publication',true)")) != "on"
            # Simulate a crash before commit: all writes and the durable schema must disappear.
            await session.rollback()
            assert await session.scalar(text("SELECT current_setting('sfa.position_publication',true)")) != "on"
            await session.rollback()
            repository = SeasonIntegrityPublicationRepository(session)
            await repository.lock()
            assert (await repository.validate(False)).fingerprint == before.fingerprint
            assert await session.scalar(text("SELECT to_regnamespace('integrity_published_2025') IS NULL"))
            await session.rollback()

        async with AsyncSession(engine) as session:
            promote, _ = get_season_integrity_publication_use_cases(session, journal)
            key, after = await promote.execute()
            await session.commit()
            assert await session.scalar(text("SELECT current_setting('sfa.position_publication',true)")) != "on"
            await session.rollback()
            (journal / "rehearsal-result.json").write_text(
                json.dumps({"journal_key": key, "fingerprint": after.fingerprint})
            )

        async with AsyncSession(engine) as session:
            _, revert = get_season_integrity_publication_use_cases(session, journal)
            _, restored = await revert.execute()
            assert restored.fingerprint == before.fingerprint
            # Exercise the exact restoration but keep the final prepared projection in the clone.
            await session.rollback()
            repository = SeasonIntegrityPublicationRepository(session)
            await repository.lock()
            assert (await repository.validate(True)).fingerprint == after.fingerprint
            assert await outside_fingerprints(session, repository) == outside_before
            await session.rollback()
    finally:
        await engine.dispose()
