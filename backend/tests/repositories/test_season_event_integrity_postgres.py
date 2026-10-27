import os
from contextlib import asynccontextmanager
from dataclasses import replace

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from sfa.domain.event_integrity import Action, ActionRevision, AppearanceRevision, IntegrityPlan
from sfa.infrastructure.repositories.ingestion_repository import IngestionRepository
from sfa.infrastructure.repositories.season_event_integrity_repository import SeasonEventIntegrityRepository


@asynccontextmanager
async def isolated_session():
    url = os.environ.get("INTEGRITY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires isolated restored 2025/2026 fixture database")
    assert make_url(url).database.endswith("_test")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            await session.begin()
            yield session
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_snapshot_scope_raw_patch_cas_and_legacy_writer_guard():
    async with isolated_session() as session:
        fixture_id = await session.scalar(text("SELECT id FROM fixtures WHERE external_id=1451024"))
        assert fixture_id is not None
        repository = SeasonEventIntegrityRepository(session)
        before = await repository.snapshot(fixture_id)
        old = next(a for a in before.actions if a.event_type == "GOAL")
        await session.execute(text("UPDATE player_events SET psxg=0.4 WHERE id=:id"), {"id": old.event_id})
        before = await repository.snapshot(fixture_id)
        corrected = Action(old.player_id, old.team_id, old.minute, old.event_type, "1:0", -1, True, 0)
        plan = IntegrityPlan(
            fixture_id, before.external_id, before.fingerprint, "source", (ActionRevision(old, corrected),), ()
        )
        assert await repository.apply(plan) == 1
        row = (
            (
                await session.execute(
                    text("SELECT id,psxg,score_before FROM player_events WHERE id=:id"), {"id": old.event_id}
                )
            )
            .mappings()
            .one()
        )
        assert row["id"] == old.event_id
        assert float(row["psxg"]) == 0.4
        assert row["score_before"] == "1:0"
        with pytest.raises(ValueError, match="CAS"):
            await repository.apply(plan)
        with pytest.raises(ValueError, match="destructive"):
            await IngestionRepository(session).delete_player_events_for_fixture(old.player_id, fixture_id)


@pytest.mark.anyio
async def test_snapshot_rejects_2026_club_fixtures():
    async with isolated_session() as session:
        fixture_id = await session.scalar(text("""
            SELECT f.id FROM fixtures f JOIN competitions c ON c.id=f.competition_id
            WHERE f.season='2026' AND c.participant_kind='club' LIMIT 1
        """))
        assert fixture_id is not None
        with pytest.raises(ValueError, match="outside season-2025"):
            await SeasonEventIntegrityRepository(session).snapshot(fixture_id)


@pytest.mark.anyio
async def test_inserted_action_is_removed_by_transaction_rollback():
    async with isolated_session() as session:
        fixture_id = await session.scalar(text("SELECT id FROM fixtures WHERE external_id=1451024"))
        repository = SeasonEventIntegrityRepository(session)
        before = await repository.snapshot(fixture_id)
        actor = next(p for p in before.appearances if p.external_id == 278)
        added = Action(actor.player_id, actor.team_id, 29, "GOAL_PENALTY", "0:1", -1, False, 1)
        plan = IntegrityPlan(
            fixture_id, before.external_id, before.fingerprint, "source", (ActionRevision(None, added),), ()
        )
        assert await repository.apply(plan) == 1
        after = await repository.snapshot(fixture_id)
        assert len(after.actions) == len(before.actions) + 1
        await session.rollback()
        restored = await repository.snapshot(fixture_id)
        assert restored.fingerprint == before.fingerprint


@pytest.mark.anyio
async def test_counter_and_extra_time_updates_are_scoped_and_rolled_back():
    async with isolated_session() as session:
        fixture_id = await session.scalar(text("SELECT id FROM fixtures WHERE external_id=1451024"))
        repository = SeasonEventIntegrityRepository(session)
        before = await repository.snapshot(fixture_id)
        actor = next(p for p in before.appearances if p.external_id == 278)
        plan = IntegrityPlan(
            fixture_id,
            before.external_id,
            before.fingerprint,
            "source",
            (),
            (),
            appearance_changes=(AppearanceRevision(actor, replace(actor, goals=actor.goals + 1)),),
            fixture_goals=(before.home_goals + 1, before.away_goals),
        )
        assert await repository.apply(plan) == 2
        after = await repository.snapshot(fixture_id)
        assert after.home_goals == before.home_goals + 1
        assert next(p for p in after.appearances if p.external_id == 278).goals == actor.goals + 1
        assert after.actions == before.actions
        await session.rollback()
        assert (await repository.snapshot(fixture_id)).fingerprint == before.fingerprint
