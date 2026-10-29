"""0070 rehearsal on a production clone named sfa_psg_titles_2025_test only.

TITLE_TEST_DATABASE_URL and TITLE_TEST_EVIDENCE_DIR are required. Each test rolls
back all changes. Provider access and production databases are prohibited.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from sfa.core.dependencies import get_competition_title_correction_use_cases
from sfa.infrastructure.repositories.player_event_score_repository import PlayerEventScoreRepository

URL = os.environ.get("TITLE_TEST_DATABASE_URL")
DIRECTORY = os.environ.get("TITLE_TEST_EVIDENCE_DIR")
pytestmark = [pytest.mark.anyio, pytest.mark.skipif(not URL or not DIRECTORY, reason="Isolated title clone required")]


def evidence():
    names = ("supercup-final", "ligue1-fixtures", "ligue1-standings",
             "intercontinental-fixtures", "intercontinental-players")
    return json.dumps({name: json.loads((Path(DIRECTORY) / (name + ".json")).read_text()) for name in names})


def engine():
    assert make_url(URL).database == "sfa_psg_titles_2025_test", "Dedicated clone required, never production"
    return create_async_engine(URL, poolclass=NullPool)


async def snapshot_rows(session):
    rows = (await session.execute(text("""
        SELECT c.name,a.phase,a.id achievement_id,b.id bonus_id,b.player_id,b.final_bonus
        FROM competition_achievements a JOIN competitions c ON c.id=a.competition_id
        JOIN player_achievement_bonuses b ON b.achievement_id=a.id
        WHERE a.season='2025' AND c.name IN('Ligue 1','UEFA Super Cup','FIFA Intercontinental Cup')
        ORDER BY a.id,b.id
    """))).all()
    return list(map(tuple, rows))


async def profiles(session):
    return (await session.execute(text("""
        SELECT p.id, sum(s.total_pts+s.achievement_bonus_pts) pts FROM sfa_season_scores s
        JOIN players p ON p.id=s.player_id JOIN competitions c ON c.id=s.competition_id
        WHERE s.rules_version_id=4 AND s.season='2025' AND c.participant_kind='club'
        GROUP BY p.id ORDER BY p.id
    """))).all()


async def test_full_title_closure_is_idempotent_rebuild_safe_and_reversible(tmp_path):
    db = engine()
    async with AsyncSession(db, expire_on_commit=False) as session:
        try:
            prepare, apply = get_competition_title_correction_use_cases(session, tmp_path)
            source = evidence()
            plan = await prepare.execute(source)
            previous_profiles = dict(await profiles(session))
            _, after = await apply.execute(plan)
            current = await snapshot_rows(session)
            psg = (await session.execute(text("""
                SELECT c.name,a.phase FROM competition_achievements a JOIN competitions c ON c.id=a.competition_id
                JOIN teams t ON t.id=a.team_id WHERE t.external_id=85 AND a.season='2025'
            """))).all()
            assert {("Ligue 1", "champion"), ("UEFA Super Cup", "winner"),
                    ("FIFA Intercontinental Cup", "winner")}.issubset(set(psg))
            assert len([r for r in psg if r.phase in {"winner", "champion"}]) == 5
            new_profiles = dict(await profiles(session))
            assert new_profiles[7571] > previous_profiles[7571]
            inter = await session.scalar(text("SELECT id FROM competitions WHERE name='FIFA Intercontinental Cup'"))
            title = (await session.execute(text("""
                SELECT s.total_pts,s.matches_played,s.achievement_bonus_pts,b.calculation_details
                FROM sfa_season_scores s JOIN player_achievement_bonuses b USING
                  (player_id,competition_id,season,rules_version_id)
                WHERE s.player_id=7571 AND s.competition_id=:inter AND s.rules_version_id=4
            """), {"inter": inter})).one()
            assert title.total_pts == 0 and title.matches_played == 0
            assert float(title.achievement_bonus_pts) == 1545
            assert title.calculation_details["team_total_minutes"] == 120
            assert title.calculation_details["performance_not_evaluated"] is True
            await PlayerEventScoreRepository(session).bulk_rebuild_season_scores(4, "2025", inter)
            assert await snapshot_rows(session) == current
            await apply.execute(await prepare.execute(source))
            assert await snapshot_rows(session) == current
            assert dict(await profiles(session)) == new_profiles
            # All rows, IDs and timestamps must match after the repeat, not only
            # headline totals. This is also the revert's optimistic CAS.
            assert (await prepare.execute(source)).before.fingerprint == after.fingerprint
            await apply.revert(plan.before, after, source)
            assert (await prepare.execute(source)).before.fingerprint == plan.before.fingerprint
        finally:
            await session.rollback()
    await db.dispose()


async def test_stale_cut_and_busy_publication_are_rejected(tmp_path):
    db = engine()
    async with AsyncSession(db, expire_on_commit=False) as first, AsyncSession(db) as second:
        try:
            prepare, apply = get_competition_title_correction_use_cases(first, tmp_path)
            plan = await prepare.execute(evidence())
            other_prepare, _ = get_competition_title_correction_use_cases(second, tmp_path / "other")
            with pytest.raises(ValueError, match="busy"):
                await other_prepare.execute(evidence())
            await second.rollback()
            await first.execute(text("UPDATE teams SET name=name||' changed' WHERE external_id=85"))
            with pytest.raises(ValueError, match="snapshot changed"):
                await apply.execute(plan)
            assert not list(tmp_path.glob("*-intent.json"))
        finally:
            await first.rollback()
            await second.rollback()
    await db.dispose()
