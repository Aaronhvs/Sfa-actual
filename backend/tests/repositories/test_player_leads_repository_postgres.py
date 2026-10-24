"""Run against an isolated PostgreSQL database named leads_test, never production.

Set LEADS_TEST_DATABASE_URL=postgresql+asyncpg://.../leads_test.
The session creates tables only there; each test rolls its data back.
"""
import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from sfa.domain.season_scope import AwardPeriodScope, ScopeKind, ScoreSource
from sfa.infrastructure.database import Base
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.enums import EventType
from sfa.infrastructure.models.events.models import PlayerEvent
from sfa.infrastructure.models.fixture_team_strengths.models import FixtureTeamStrength
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.player_event_scores.models import PlayerEventScore
from sfa.infrastructure.models.player_positions.models import PlayerPositionAssignment
from sfa.infrastructure.models.player_stats.models import PlayerStats
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.scores.models import SFASeasonScore
from sfa.infrastructure.models.scoring_rules.models import ScoringRulesVersion
from sfa.infrastructure.models.teams.models import Team
from sfa.infrastructure.repositories.player_leads_repository import PlayerLeadsRepository

URL = os.environ.get("LEADS_TEST_DATABASE_URL")
pytestmark = [pytest.mark.anyio, pytest.mark.skipif(not URL, reason="Isolated PostgreSQL URL not supplied")]
NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)
SEASON = "2025"
SCOPE = AwardPeriodScope("season-2025", "2025/26", ScopeKind.AWARD_PERIOD,
                         (ScoreSource(SEASON, (140, 2, 350)),), is_latest=True, includes_world_cup=True)


@pytest.fixture(scope="session")
def leads_database():
    assert make_url(URL).database == "leads_test", "Dedicated leads_test database required"

    async def initialize():
        engine = create_async_engine(URL, poolclass=NullPool)
        async with engine.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
            await connection.run_sync(Base.metadata.create_all)
            # Execute the actual deployed migrations, not test substitutes for
            # position functions. This database is explicitly isolated above.
            raw = await connection.get_raw_connection()
            migrations = Path(__file__).resolve().parents[2] / "migrations"
            for filename, marker in (
                ("0052_durable_position_evidence.sql", "ix_position_assignment_lookup"),
                ("0053_position_correction_publication.sql", "position_correction_batches"),
                ("0054_season_position_pilot.sql", "position_scope_classifications"),
            ):
                if not await connection.scalar(text("SELECT to_regclass(:marker)"), {"marker": marker}):
                    sql = (migrations / filename).read_text(encoding="utf-8").strip()
                    assert sql.startswith("BEGIN;") and sql.endswith("COMMIT;")
                    await raw.driver_connection.execute(sql[6:-7])
        await engine.dispose()

    asyncio.run(initialize())
    return URL


@asynccontextmanager
async def rolled_back_session(url):
    # Opened inside each test so the connection lives on the test's own event loop.
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as db:
            async with db.begin():
                yield db
                await db.rollback()
    finally:
        await engine.dispose()


def _strength(fixture_id, team_id, competition_id, value):
    return FixtureTeamStrength(
        fixture_id=fixture_id, team_id=team_id, season=SEASON, competition_id=competition_id,
        participant_kind="club" if competition_id != 350 else "national_team", pre_match_elo_raw=1500,
        post_match_elo_raw=1500, pre_match_strength=value, post_match_strength=value, model_version="test",
        seed_source="test", created_at=NOW,
    )


def _event(event_id, player_id, fixture_id, event_type=EventType.GOAL):
    return PlayerEvent(id=event_id, player_id=player_id, fixture_id=fixture_id, team_id=1, minute=10,
                       event_type=event_type, m1=1, m2=1, m3=1, m4=1, mvisit=1, pts=10)


def _score(event_id, player_id, fixture_id, rules_version_id, points, competition_id=140):
    return PlayerEventScore(
        event_id=event_id, player_id=player_id, fixture_id=fixture_id, season=SEASON,
        competition_id=competition_id, rules_version_id=rules_version_id, action_type="goal", position="EXT",
        base_points=10, m1=1, m2=1, m3=1, m4=1, mvisit=1, mrating=1, combined_before_clamp=1,
        combined_after_clamp=1, final_points=points, created_at=NOW,
    )


async def seed(db):
    db.add_all([
        Competition(id=140, name="La Liga", country="ES", participant_kind="club"),
        Competition(id=2, name="Champions League", country="EU", participant_kind="club"),
        Competition(id=350, name="World Cup", country="WO", participant_kind="national_team"),
    ])
    await db.flush()
    db.add_all([
        Team(id=1, name="Club", competition_id=140), Team(id=2, name="Mid", competition_id=140),
        Team(id=3, name="Big", competition_id=140), Team(id=4, name="Elite", competition_id=140),
        Team(id=5, name="Unknown", competition_id=140), Team(id=6, name="Germany", competition_id=350),
        Team(id=7, name="Spain", competition_id=350), Team(id=9, name="Stranger", competition_id=140),
    ])
    db.add_all([ScoringRulesVersion(id=v, name=f"Rules {v}", version=str(v), config_json={}, created_at=NOW)
                for v in (7, 8)])
    db.add_all([Player(id=1, name="Striker", position="EXT"), Player(id=2, name="Joshua Kimmich", position="MC")])
    await db.flush()
    rivals = {1: 2, 2: 3, 3: 4, 4: 5, 5: 2, 6: 2, 7: 2}
    db.add_all([
        Fixture(id=fixture_id, external_id=fixture_id, competition_id=140, home_team_id=1, away_team_id=rival,
                stage="Regular Season", season=SEASON, played_at=NOW + timedelta(days=fixture_id),
                status="1H" if fixture_id == 5 else "FT")
        for fixture_id, rival in rivals.items()
    ])
    db.add(Fixture(id=20, external_id=20, competition_id=350, home_team_id=6, away_team_id=7, stage="Group",
                   season=SEASON, played_at=NOW, status="FT"))
    await db.flush()
    db.add_all([_strength(1, 2, 140, 49.99), _strength(2, 3, 140, 50), _strength(3, 4, 140, 70)])
    stats = [
        # fixture, goals, shots_on, minutes, team
        (1, 2, 3, 90, 1),   # one of the goals is a penalty
        (2, 2, 1, 90, 1),   # provider reports more goals than shots on target
        (3, 1, 2, 90, 1),
        (4, 0, 0, 90, 1),   # rival without strength snapshot
        (5, 3, 3, 90, 1),   # live fixture: excluded
        (6, 1, 1, 0, 1),    # zero minutes: excluded
        (7, 1, 1, 90, 9),   # team not playing the fixture: excluded
    ]
    db.add_all([PlayerStats(player_id=1, fixture_id=f, season=SEASON, team_id=team, goals=g, shots_on=s,
                            minutes=m, duels_won=3, duels_total=2) for f, g, s, m, team in stats])
    db.add(PlayerStats(player_id=2, fixture_id=20, season=SEASON, team_id=6, minutes=90))
    db.add_all([_event(1, 1, 1, EventType.GOAL_PENALTY), _event(2, 1, 1), _event(3, 1, 2), _event(4, 1, 3)])
    await db.flush()
    db.add_all([_score(2, 1, 1, 7, 30), _score(3, 1, 2, 7, 100), _score(3, 1, 2, 8, 999), _score(4, 1, 3, 7, 50)])
    db.add(SFASeasonScore(player_id=1, competition_id=140, team_id=1, season=SEASON, rules_version_id=7,
                          total_pts=180, matches_played=4, last_updated=NOW))
    await db.flush()
    return PlayerLeadsRepository(db)


async def test_samples_apply_population_penalties_and_big_games(leads_database):
    async with rolled_back_session(leads_database) as session:
        repo = await seed(session)
        samples = {(s.player_id, s.competition_id): s for s in await repo.get_competition_samples(SCOPE, 7)}
        striker = samples[(1, 140)]
        assert striker.matches == 4 and striker.minutes == 360
        assert striker.goals == 5 and striker.penalty_goals == 1 and striker.np_goals == 4
        assert striker.np_shots_on == 6  # (3-1) + max(1, 2) + 2 + 0
        assert striker.duels_total >= striker.duels_won
        assert striker.big_matches == 2 and striker.elite_matches == 1 and striker.big_minutes == 180
        assert striker.big_points == 150  # 100 + 50 of version 7; 49.99 rival and version 8 ignored
        assert striker.position == "EXT" and striker.participant_kind == "club"
        kimmich = samples[(2, 350)]
        assert kimmich.position == "LAT"  # World Cup override


async def test_without_rules_version_big_games_are_zero(leads_database):
    async with rolled_back_session(leads_database) as session:
        repo = await seed(session)
        striker = next(s for s in await repo.get_competition_samples(SCOPE, None) if s.player_id == 1)
        assert striker.big_points == 0 and striker.big_matches == 0


async def test_scope_positions_use_club_teams(leads_database):
    async with rolled_back_session(leads_database) as session:
        repo = await seed(session)
        positions = await repo.get_scope_positions(SCOPE)
        assert positions[1] == "EXT"
        assert 2 not in positions  # only national-team appearances
        tournament = AwardPeriodScope("world-cup-2025", "Mundial", ScopeKind.TOURNAMENT, (ScoreSource(SEASON, (350,)),))
        assert await repo.get_scope_positions(tournament) == {}


async def test_stamp_changes_with_new_scores(leads_database):
    async with rolled_back_session(leads_database) as session:
        repo = await seed(session)
        first = await repo.get_data_stamp(SCOPE, 7)
        assert first == await repo.get_data_stamp(SCOPE, 7)
        session.add(SFASeasonScore(player_id=2, competition_id=350, team_id=6, season=SEASON, rules_version_id=7,
                                   total_pts=10, matches_played=1, last_updated=NOW))
        await session.flush()
        assert await repo.get_data_stamp(SCOPE, 7) != first
        assert await repo.get_data_stamp(SCOPE, None) != first


async def publish_role(db, *, competition_id=None, effective_from=None, effective_until=None,
                       position="MC", batch_status="published"):
    await db.execute(text("SET LOCAL sfa.position_publication = 'on'"))
    await db.execute(text("""
        INSERT INTO position_correction_batches
            (batch_id, manifest_hash, manifest, before_image, after_image, status, actor)
        VALUES ('leads-regression', 'test', '{}', '{}', '{}', :status, 'test')
    """), {"status": batch_status})
    db.add(PlayerPositionAssignment(
        player_id=1, team_id=1, competition_id=competition_id, season=SEASON, position=position,
        status="accepted", effective_from=effective_from or NOW - timedelta(days=365),
        effective_until=effective_until, revision_id="leads-regression", source_kind="manual",
        reason="Regression: stored DC must not override the published role", actor="test", created_at=NOW,
        publication_batch_id="leads-regression",
    ))
    await db.flush()


async def test_stored_dc_uses_published_mc_in_samples_and_scope(leads_database):
    async with rolled_back_session(leads_database) as session:
        repo = await seed(session)
        player = await session.get(Player, 1)
        player.position = "DC"
        await session.flush()
        await publish_role(session)
        samples = await repo.get_competition_samples(SCOPE, 7)
        assert next(s for s in samples if s.player_id == 1).position == "MC"
        assert (await repo.get_scope_positions(SCOPE))[1] == "MC"
        assert player.position == "DC"  # Read projection does not rewrite the catalog.


async def test_published_scope_classification_overrides_legacy_dc(leads_database):
    async with rolled_back_session(leads_database) as session:
        repo = await seed(session)
        player = await session.get(Player, 1)
        player.position = "DC"
        await session.flush()
        await db_scope_classification(session)
        samples = await repo.get_competition_samples(SCOPE, 7)
        assert next(s for s in samples if s.player_id == 1).position == "MC"
        assert (await repo.get_scope_positions(SCOPE))[1] == "MC"


async def db_scope_classification(db):
    await db.execute(text("SET LOCAL sfa.position_publication = 'on'"))
    await db.execute(text("""
        INSERT INTO position_correction_batches
            (batch_id, manifest_hash, manifest, before_image, after_image, status, actor)
        VALUES ('scope-regression', 'test', '{}', '{}', '{}', 'published', 'test')
    """))
    await db.execute(text("""
        INSERT INTO position_scope_classifications
            (player_id, team_id, scope_key, position, competition_ids, scope_competition_ids,
             decision_id, definition, batch_id)
        VALUES (1, 1, 'season-2025', 'MC', ARRAY[140], ARRAY[2,140,350], 'test', '{}', 'scope-regression')
    """))


async def test_historical_scope_uses_scope_as_of_instead_of_now(leads_database):
    async with rolled_back_session(leads_database) as session:
        repo = await seed(session)
        await session.execute(update(Fixture).values(played_at=datetime(2000, 1, 1, tzinfo=timezone.utc)))
        await publish_role(session, effective_from=datetime(1999, 1, 1, tzinfo=timezone.utc),
                           effective_until=datetime(2001, 1, 1, tzinfo=timezone.utc))
        historical = replace(SCOPE, is_latest=False)
        assert next(s for s in await repo.get_competition_samples(historical, 7) if s.player_id == 1).position == "MC"
        assert (await repo.get_scope_positions(historical))[1] == "MC"
        assert (await repo.get_scope_positions(SCOPE))[1] == "EXT"


async def test_competition_specific_role_does_not_leak_to_other_competitions(leads_database):
    async with rolled_back_session(leads_database) as session:
        repo = await seed(session)
        await publish_role(session, competition_id=2)
        assert next(s for s in await repo.get_competition_samples(SCOPE, 7) if s.player_id == 1).position == "EXT"
        assert (await repo.get_scope_positions(SCOPE))[1] == "EXT"


async def test_reverted_publication_does_not_override_legacy_position(leads_database):
    async with rolled_back_session(leads_database) as session:
        repo = await seed(session)
        await publish_role(session, batch_status="reverted")
        assert next(s for s in await repo.get_competition_samples(SCOPE, 7) if s.player_id == 1).position == "EXT"
        assert (await repo.get_scope_positions(SCOPE))[1] == "EXT"


async def test_scope_fallback_uses_highest_scoring_club_competition(leads_database):
    async with rolled_back_session(leads_database) as session:
        repo = await seed(session)
        await publish_role(session, competition_id=140)
        session.add(Fixture(id=30, external_id=30, competition_id=2, home_team_id=1, away_team_id=2,
                            season=SEASON, stage="Group", played_at=NOW + timedelta(days=30), status="FT"))
        await session.flush()
        session.add(PlayerStats(player_id=1, fixture_id=30, team_id=1, season=SEASON, minutes=90))
        # Latest appearance is in Champions, but the highest scoring competition
        # remains La Liga, exactly as in the ranking's aggregate.
        score = SFASeasonScore(player_id=1, competition_id=2, team_id=1, season=SEASON, rules_version_id=7,
                               total_pts=10, matches_played=1, last_updated=NOW)
        session.add(score)
        await session.flush()
        samples = {s.competition_id: s for s in await repo.get_competition_samples(SCOPE, 7) if s.player_id == 1}
        assert samples[140].position == "MC" and samples[2].position == "EXT"
        assert (await repo.get_scope_positions(SCOPE))[1] == "MC"
        score.total_pts = 1000
        await session.flush()
        assert (await repo.get_scope_positions(SCOPE))[1] == "EXT"
