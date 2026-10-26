"""Integration tests require MVP_TEST_DATABASE_URL pointing exclusively to mvps_test."""
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import delete, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from sfa.domain.matchday_mvp import group_rounds, select_mvps
from sfa.domain.season_scope import AwardPeriodScope, ScopeKind, ScoreSource
from sfa.infrastructure.database import Base
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.enums import EventType
from sfa.infrastructure.models.events.models import PlayerEvent
from sfa.infrastructure.models.fixture_team_strengths.models import FixtureTeamStrength
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.player_event_scores.models import PlayerEventScore
from sfa.infrastructure.models.player_stats.models import PlayerStats
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.scoring_rules.models import ScoringRulesVersion
from sfa.infrastructure.models.teams.models import Team
from sfa.infrastructure.repositories.matchday_mvp_repository import MatchdayMvpRepository
from sfa.infrastructure.repositories.player_leads_repository import PlayerLeadsRepository

URL = os.environ.get("MVP_TEST_DATABASE_URL")
pytestmark = [pytest.mark.anyio, pytest.mark.skipif(not URL, reason="Isolated mvps_test URL not supplied")]
NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)
SCOPE = AwardPeriodScope("season-2026", "2026/2027", ScopeKind.AWARD_PERIOD,
                         (ScoreSource("2026", (1, 2)),), is_latest=True)


@pytest.fixture(scope="session")
def mvp_database():
    assert make_url(URL).database == "mvps_test", "Dedicated mvps_test database required, never production"

    async def initialize():
        engine = create_async_engine(URL, poolclass=NullPool)
        async with engine.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
            await connection.run_sync(Base.metadata.create_all)
            raw = await connection.get_raw_connection()
            migrations = Path(__file__).resolve().parents[2] / "migrations"
            for filename, marker in (
                ("0052_durable_position_evidence.sql", "ix_position_assignment_lookup"),
                ("0053_position_correction_publication.sql", "position_correction_batches"),
                ("0054_season_position_pilot.sql", "position_scope_classifications"),
            ):
                if not await connection.scalar(text("SELECT to_regclass(:marker)"), {"marker": marker}):
                    sql = (migrations / filename).read_text(encoding="utf-8").strip()
                    await raw.driver_connection.execute(sql[6:-7])
        await engine.dispose()

    asyncio.run(initialize())
    return URL


@pytest.fixture
def db(mvp_database):
    return mvp_database


@asynccontextmanager
async def rolled_back_session(url):
    engine = create_async_engine(url, poolclass=NullPool)
    async with AsyncSession(engine) as session:
        async with session.begin():
            yield session
            await session.rollback()
    await engine.dispose()


async def seed(db):
    db.add_all([Competition(id=1, name="La Liga", country="ES", participant_kind="club"),
                Competition(id=2, name="Champions League", country="EU", participant_kind="club")])
    await db.flush()
    db.add_all([Team(id=1, external_id=529, name="Barcelona", competition_id=1),
                Team(id=2, external_id=541, name="Madrid", competition_id=1),
                Team(id=3, external_id=500, name="New club", competition_id=1),
                ScoringRulesVersion(id=7, name="Published", version="7", config_json={}, created_at=NOW),
                ScoringRulesVersion(id=8, name="Other", version="8", config_json={}, created_at=NOW)])
    await db.flush()
    db.add_all([Player(id=1, name="Stored central", position="DC", team_id=3),
                Player(id=2, name="Forward", position="DEL")])
    db.add_all([Fixture(id=i, external_id=1000 + i, competition_id=1, home_team_id=2, away_team_id=1,
                        stage="regular", season="2026", matchday=1 if i < 3 else 2,
                        played_at=NOW + timedelta(days=i), status="FT" if i == 1 else "NS",
                        home_goals=1 if i == 1 else None, away_goals=2 if i == 1 else None) for i in (1, 2, 3)])
    await db.flush()
    for eid, pid, fid, kind, before in [(1, 1, 1, EventType.GOAL, "1:0"),
                                      (2, 1, 1, EventType.STATS, None),
                                      (3, 2, 1, EventType.GOAL, "0:0"),
                                      (4, 2, 1, EventType.STATS, None),
                                      (5, 2, 3, EventType.STATS, None)]:
        db.add(PlayerEvent(id=eid, player_id=pid, fixture_id=fid, team_id=1, minute=61 if eid == 1 else 90,
                           event_type=kind, score_before=before, score_diff=0, m1=1, m2=1, m3=1, m4=1,
                           mvisit=1.3, pts=1))
    await db.flush()
    for sid, eid, pid, fid, version, pts, action in [(1, 1, 1, 1, 7, 100, "goal"), (2, 2, 1, 1, 7, 900, "stats"),
                                                   (3, 3, 2, 1, 7, 800, "goal"), (4, 4, 2, 1, 7, 100, "stats"),
                                                   (5, 5, 2, 3, 7, 9999, "stats"),
                                                   (6, 3, 2, 1, 8, 9999, "goal")]:
        db.add(PlayerEventScore(id=sid, event_id=eid, player_id=pid, fixture_id=fid, season="2026", competition_id=1,
                                rules_version_id=version, action_type=action, position="DC", base_points=1,
                                m1=1, m2=1, m3=1, m4=1, mvisit=1.3, mrating=1, combined_before_clamp=1,
                                combined_after_clamp=1, final_points=pts, created_at=NOW))
    db.add_all([PlayerStats(player_id=pid, fixture_id=1, team_id=1, season="2026", minutes=90, goals=1, assists=0)
                for pid in (1, 2)])
    db.add(FixtureTeamStrength(fixture_id=1, team_id=2, season="2026", competition_id=1, participant_kind="club",
                               pre_match_elo_raw=1500, post_match_elo_raw=1500, pre_match_strength=50,
                               post_match_strength=80, model_version="test", seed_source="test", created_at=NOW))
    await db.flush()
    return MatchdayMvpRepository(db, PlayerLeadsRepository(db))


async def publish_scope_position(db):
    await db.execute(text("SET LOCAL sfa.position_publication = 'on'"))
    await db.execute(text("""
        INSERT INTO position_correction_batches
          (batch_id,manifest_hash,manifest,before_image,after_image,status,actor)
        VALUES ('mvp-test','test','{}','{}','{}','published','test')
    """))
    await db.execute(text("""
        INSERT INTO position_scope_classifications
          (player_id,team_id,scope_key,position,competition_ids,scope_competition_ids,decision_id,definition,batch_id)
        VALUES (1,1,'season-2026','MC',ARRAY[1],ARRAY[1,2],'test','{}','mvp-test')
    """))


async def test_stats_sum_one_version_finished_only_and_actual_appearance_team(db):
    async with rolled_back_session(db) as db:
        repo = await seed(db)
        performances = await repo.get_performances(1, "2026", 7)
        assert len(performances) == 2
        assert {p.player_id: p.points for p in performances} == {1: 1000, 2: 900}
        assert performances[0].team_id == 1  # Player.team_id is the later club 3.
        fixtures = await repo.get_fixtures(1, "2026")
        assert fixtures[0].home_team.id == 2 and fixtures[0].home_team.external_id == 541
        item, = select_mvps(group_rounds("La Liga", fixtures), performances, {})
        assert item.sfa_pts == 1000 and item.pending_fixtures == 1 and not item.complete
        assert item.reasons == ("big_rival", "behind", "away")
        assert await repo.competition_exists(2)
        assert not await repo.competition_exists(999)
        assert await repo.get_performances(2, "2026", 7) == ()
        assert await repo.get_fixtures(1, "1900") == ()


async def test_published_scope_position_same_shared_projection_as_leads(db):
    async with rolled_back_session(db) as db:
        repo = await seed(db)
        await publish_scope_position(db)
        positions = await repo.get_positions(SCOPE, 1)
        assert positions[1] == "MC"
        assert (await db.get(Player, 1)).position.value == "DC"
        assert (await PlayerLeadsRepository(db).get_competition_positions(SCOPE, 1))[(1, "2026", 1)] == "MC"
        assert await repo.get_positions(SCOPE, 2) == {}


async def test_missing_stats_falls_back_to_verified_events_and_conflicting_team_excludes(db):
    async with rolled_back_session(db) as db:
        repo = await seed(db)
        await db.execute(delete(PlayerStats).where(PlayerStats.player_id == 1))
        row = next(p for p in await repo.get_performances(1, "2026", 7) if p.player_id == 1)
        assert row.goals == 1 and row.assists == 0 and row.team_id == 1 and row.points == 1000
        db.add(PlayerStats(player_id=1, fixture_id=1, team_id=2, season="2026", minutes=90))
        await db.flush()
        assert [p.player_id for p in await repo.get_performances(1, "2026", 7)] == [2]


async def test_highest_decisive_action_context_not_stats_or_final_score_or_imputed_zero(db):
    async with rolled_back_session(db) as db:
        repo = await seed(db)
        await db.execute(update(PlayerEventScore).where(PlayerEventScore.id == 1).values(final_points=1100))
        await db.execute(update(PlayerEvent).where(PlayerEvent.id == 2).values(event_type=EventType.ASSIST,
                                                                             score_before="1:1", minute=75))
        await db.execute(update(PlayerEventScore).where(PlayerEventScore.id == 2).values(action_type="assist"))
        # goal 1100 beats assist 900; player was behind before that goal, despite winning the game.
        row = next(p for p in await repo.get_performances(1, "2026", 7) if p.player_id == 1)
        assert row.decisive_score_diff == -1
        await db.execute(update(PlayerEventScore).where(PlayerEventScore.id == 2).values(final_points=1200))
        row = next(p for p in await repo.get_performances(1, "2026", 7) if p.player_id == 1)
        assert row.decisive_score_diff == 0
        await db.execute(update(PlayerEvent).where(PlayerEvent.id == 2).values(score_before=None, score_diff=0))
        row = next(p for p in await repo.get_performances(1, "2026", 7) if p.player_id == 1)
        assert row.decisive_score_diff is None


async def test_fingerprint_changes_for_same_sum_in_place_updates_fixture_completion_and_positions(db):
    async with rolled_back_session(db) as db:
        repo = await seed(db)
        before = await repo.get_data_stamp(SCOPE, 1, "2026", 7)
        await db.execute(update(PlayerEventScore).where(PlayerEventScore.id == 1).values(final_points=200))
        await db.execute(update(PlayerEventScore).where(PlayerEventScore.id == 2).values(final_points=800))
        recalculated = await repo.get_data_stamp(SCOPE, 1, "2026", 7)
        assert recalculated != before  # count, max ID, timestamps and global sum all remained unchanged.
        await db.execute(update(Fixture).where(Fixture.id == 2).values(status="FT"))
        finished = await repo.get_data_stamp(SCOPE, 1, "2026", 7)
        assert finished != recalculated
        await publish_scope_position(db)
        assert await repo.get_data_stamp(SCOPE, 1, "2026", 7) != finished
        assert await repo.get_data_stamp(SCOPE, 1, "2026", 8) != await repo.get_data_stamp(SCOPE, 1, "2026", 7)
