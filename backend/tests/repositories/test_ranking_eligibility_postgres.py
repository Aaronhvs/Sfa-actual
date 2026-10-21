"""Run against an isolated PostgreSQL database named ranking_test, never production.

Set RANKING_TEST_DATABASE_URL=postgresql+asyncpg://.../ranking_test.
The session creates tables only there; each test rolls its data back.
"""
import asyncio
import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from sfa.application.use_cases.get_ranking import GetRankingUseCase
from sfa.domain.ranking_eligibility import ranking_min_matches
from sfa.domain.season_scope import AwardPeriodScope, ScopeKind, ScoreSource
from sfa.infrastructure.database import Base
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.individual_honors.models import IndividualHonorModel
from sfa.infrastructure.models.player_stats.models import PlayerStats
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.scores.models import SFASeasonScore
from sfa.infrastructure.models.scoring_rules.models import ScoringRulesVersion
from sfa.infrastructure.models.teams.models import Team
from sfa.infrastructure.repositories.sfa_score_repository import SFAScoreRepository

URL = os.environ.get("RANKING_TEST_DATABASE_URL")
pytestmark = [pytest.mark.anyio, pytest.mark.skipif(not URL, reason="Isolated PostgreSQL URL not supplied")]
NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)


@pytest.fixture(scope="session")
def ranking_database():
    assert make_url(URL).database == "ranking_test", "Dedicated ranking_test database required"

    async def initialize():
        engine = create_async_engine(URL, poolclass=NullPool)
        async with engine.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(initialize())
    return URL


@pytest.fixture
async def ranking_session(ranking_database):
    engine = create_async_engine(ranking_database, poolclass=NullPool)
    async with AsyncSession(engine) as session:
        async with session.begin():
            yield session
            await session.rollback()
    await engine.dispose()


async def seed(session, maximum=12, competition=1, season="2026"):
    minimum = ranking_min_matches(maximum)
    session.add(Competition(id=competition, name=f"Competition {competition}", country="ES",
                            participant_kind="national_team" if competition == 350 else "club"))
    await session.flush()
    session.add_all([Team(id=1, name="Spain" if competition == 350 else "Club", competition_id=competition),
                     Team(id=2, name="Opponent", competition_id=competition)])
    session.add_all([ScoringRulesVersion(id=v, name=f"Rules {v}", version=str(v), config_json={}, created_at=NOW)
                     for v in (7, 8)])
    await session.flush()
    # Positivity, boundary, low sample, bonus sign change, honor sign change, legacy override.
    values = [(1, "Leader", "MC", maximum, 100, 0),
              (2, "Boundary", "DEL", minimum, 200, 0),
              (3, "Low sample", "DEL", max(1, minimum-1), 300, 0),
              (4, "Zero", "DC", maximum, 0, 0),
              (5, "Bonus", "DC", maximum, -5, 10),
              (6, "Honor", "DC", maximum, -7, 0),
              (7, "Fermín López", "EXT", maximum, 150, 0)]
    session.add_all([Player(id=pid, name=name, position=position) for pid, name, position, *_ in values])
    await session.flush()
    session.add_all([Fixture(id=i, external_id=i, competition_id=competition, home_team_id=1, away_team_id=2,
                             stage="Regular Season", season=season, played_at=NOW, status="FT")
                     for i in range(1, maximum+1)])
    await session.flush()
    for pid, name, position, matches, points, bonus in values:
        session.add(SFASeasonScore(player_id=pid, competition_id=competition, team_id=1, season=season,
                                   rules_version_id=7, total_pts=points, achievement_bonus_pts=bonus,
                                   matches_played=matches, breakdown={"goal": {"count": 1}}, last_updated=NOW))
        session.add_all([PlayerStats(player_id=pid, fixture_id=i, season=season, team_id=1, minutes=90)
                         for i in range(1, matches+1)])
    # A second rules version must not increase the maximum or duplicate players.
    session.add(SFASeasonScore(player_id=1, competition_id=competition, team_id=1, season=season,
                               rules_version_id=8, total_pts=9999, matches_played=99, last_updated=NOW))
    await session.flush()
    return SFAScoreRepository(session)


@pytest.mark.parametrize("maximum,expected", [(1, 1), (12, 3), (30, 5)])
async def test_season_boundary_count_pages_and_positive_points(ranking_session, maximum, expected):
    repo = await seed(ranking_session, maximum)
    result = await GetRankingUseCase(repo, default_rules_version_id=7).execute(season="2026")
    assert result.min_matches == expected
    assert result.total == len(result.ranking)
    assert all(p.total_pts > 0 and p.matches_played >= expected for p in result.ranking)
    assert (3 in {p.player_id for p in result.ranking}) == (expected == 1)
    pages = []
    for offset in range(result.total):
        pages.extend(await repo.get_ranking("2026", limit=1, offset=offset, rules_version_id=7,
                                            min_matches=expected))
    assert [p.player_id for p in pages] == [p.player_id for p in result.ranking]


async def test_name_bypasses_only_minimum_and_blank_does_not(ranking_session):
    repo = await seed(ranking_session)
    use_case = GetRankingUseCase(repo, default_rules_version_id=7)
    result = await use_case.execute(season="2026", name="  Low sample  ")
    assert result.min_matches == 0 and result.total == 1 and result.ranking[0].player_id == 3
    assert (await use_case.execute(season="2026", name="Zero")).total == 0
    assert (await use_case.execute(season="2026", name="Bonus")).total == 0
    assert (await use_case.execute(season="2026", name="   ")).min_matches == 3


@pytest.mark.parametrize("use_total,expected_ids", [(False, {1, 2, 7}), (True, {1, 2, 5, 6, 7})])
async def test_contextual_points_include_honors_only_in_total_mode(ranking_session, use_total, expected_ids):
    repo = await seed(ranking_session)
    scope = AwardPeriodScope("season-2026", "2026/2027", ScopeKind.AWARD_PERIOD, (ScoreSource("2026", (1,)),))
    ranking_session.add(IndividualHonorModel(
        player_id=6, scope_key=scope.key, scope_label=scope.label, context_key="test", context_label="Test",
        scope_category="club", honor_type="goals", source_season="2026", competition_id=1,
        rules_version_id=7, metric_value=1, raw_bonus_pts=10, awarded_bonus_pts=10))
    await ranking_session.flush()
    rows = await repo.get_ranking_for_scope(scope, rules_version_id=7, min_matches=3, use_total=use_total)
    total = await repo.get_ranking_total_for_scope(scope, rules_version_id=7, min_matches=3, use_total=use_total)
    assert total == len(rows) == len(expected_ids)
    assert {p.player_id for p in rows} == expected_ids


async def test_position_override_filtered_before_page_and_count(ranking_session):
    repo = await seed(ranking_session)
    for position, expected in [("MCO", {7}), ("EXT", set()), ("DC", {5})]:
        rows = await repo.get_ranking("2026", position=position, rules_version_id=7,
                                      use_total=True, min_matches=3, limit=1)
        total = await repo.get_ranking_total("2026", position=position, rules_version_id=7,
                                            use_total=True, min_matches=3)
        assert {p.player_id for p in rows} == expected
        assert len(rows) == total


async def test_world_cup_scope_computes_own_maximum(ranking_session):
    repo = await seed(ranking_session, maximum=7, competition=350)
    scope = AwardPeriodScope("world-cup-2026", "Mundial 2026", ScopeKind.TOURNAMENT,
                             (ScoreSource("2026", (350,)),))

    class Seasons:
        async def resolve_scope(self, key=None):
            return scope

    result = await GetRankingUseCase(repo, 7, Seasons()).execute(scope=scope.key)
    assert result.min_matches == 2 and result.scope == scope.key
    assert result.total == len(result.ranking) == 3
    assert all(p.matches_played >= 2 for p in result.ranking)


async def test_all_history_count_list_and_name_bypass(ranking_session):
    repo = await seed(ranking_session)
    use_case = GetRankingUseCase(repo, default_rules_version_id=7)
    result = await use_case.execute(scope="all", use_total=True)
    assert result.min_matches == 3 and result.total == len(result.ranking) == 4
    result = await use_case.execute(scope="all", name="Low sample")
    assert result.min_matches == 0 and result.total == len(result.ranking) == 1
    rows = await repo.get_ranking_all_seasons(position="MCO", min_matches=3, rules_version_id=7)
    assert [r.player_id for r in rows] == [7]
    assert await repo.get_ranking_total_all_seasons(position="MCO", min_matches=3, rules_version_id=7) == 1


async def test_competition_filter_applies_before_maximum_and_not_name_or_position(ranking_session):
    repo = await seed(ranking_session)
    ranking_session.add(Competition(id=2, name="Cup", country="ES"))
    await ranking_session.flush()
    ranking_session.add(SFASeasonScore(player_id=1, competition_id=2, team_id=1, season="2026",
                                       rules_version_id=7, total_pts=10, matches_played=18, last_updated=NOW))
    await ranking_session.flush()
    assert await repo.get_ranking_max_matches(season="2026", competition_id=1, rules_version_id=7) == 12
    assert await repo.get_ranking_max_matches(season="2026", rules_version_id=7) == 30
    result = await GetRankingUseCase(repo, 7).execute(season="2026", competition_id=1, position="DEL")
    assert result.min_matches == 3 and result.total == 1
