"""Uses only the recent isolated audit clone; all synthetic rows are rolled back."""
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from sfa.domain.season_scope import AwardPeriodScope, ScopeKind, ScoreSource
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.enums import EventType
from sfa.infrastructure.models.events.models import PlayerEvent
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.player_event_scores.models import PlayerEventScore
from sfa.infrastructure.models.player_stats.models import PlayerStats
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.scores.models import SFASeasonScore
from sfa.infrastructure.models.scoring_rules.models import ScoringRulesVersion
from sfa.infrastructure.models.teams.models import Team
from sfa.infrastructure.repositories.sfa_score_repository import SFAScoreRepository

URL = os.environ.get("RANK_MOVEMENT_TEST_DATABASE_URL")
pytestmark = [pytest.mark.anyio, pytest.mark.skipif(not URL, reason="Isolated audit clone URL required")]
BASE = 2_000_000_000
SEASON = "2099"


@asynccontextmanager
async def movement_session():
    assert make_url(URL).database == "casseres_position_test", "Never use an application database"
    engine = create_async_engine(URL, poolclass=NullPool,
                                 connect_args={"server_settings": {"statement_timeout": "5000"}})
    try:
        async with AsyncSession(engine) as session:
            async with session.begin():
                yield session
                await session.rollback()
    finally:
        await engine.dispose()


async def seed(session):
    now = datetime.now(timezone.utc)
    session.add(Competition(id=BASE, name="Movement League", country="ES", participant_kind="club"))
    session.add(ScoringRulesVersion(id=BASE, name="Movement Rules", version="movement-test", config_json={},
                                   created_at=now, is_active=False))
    await session.flush()
    session.add_all([Team(id=BASE, external_id=BASE, name="Movement Club", competition_id=BASE),
                     Team(id=BASE + 1, external_id=BASE + 1, name="Movement Rival", competition_id=BASE)])
    session.add_all([Player(id=BASE + i, external_id=BASE + i, name=f"Movement {i}", position="MC")
                     for i in range(1, 4)])
    await session.flush()
    session.add_all([Fixture(id=BASE + i, external_id=BASE + i, competition_id=BASE, season=SEASON,
                            home_team_id=BASE, away_team_id=BASE + 1, played_at=now - timedelta(days=days),
                            stage="regular", status="FT") for i, days in [(1, 10), (2, 1)]])
    await session.flush()
    # B has two scoring events in one recent fixture: appearances must remain distinct.
    entries = [(1, 1, 100), (2, 1, 90), (2, 2, 23), (2, 2, 7), (3, 2, 200)]
    for index, (player, fixture, points) in enumerate(entries, 1):
        session.add(PlayerEvent(id=BASE + index, player_id=BASE + player, fixture_id=BASE + fixture,
                                team_id=BASE, minute=index, event_type=EventType.STATS,
                                m1=1, m2=1, m3=1, m4=1, mvisit=1, pts=points))
    await session.flush()
    for index, (player, fixture, points) in enumerate(entries, 1):
        session.add(PlayerEventScore(id=BASE + index, event_id=BASE + index, player_id=BASE + player,
                                    fixture_id=BASE + fixture, competition_id=BASE, season=SEASON,
                                    rules_version_id=BASE, action_type="stats", position="MC", base_points=points,
                                    m1=1, m2=1, m3=1, m4=1, mvisit=1, mrating=1, combined_before_clamp=1,
                                    combined_after_clamp=1, final_points=points, created_at=now))
    for player, total, fixtures in [(1, 100, [1]), (2, 120, [1, 2]), (3, 200, [2])]:
        session.add(SFASeasonScore(player_id=BASE + player, competition_id=BASE, team_id=BASE,
                                   season=SEASON, rules_version_id=BASE, total_pts=total,
                                   achievement_bonus_pts=0, matches_played=len(fixtures),
                                   breakdown={"goal": {"count": 1}}, last_updated=now))
        for fixture in fixtures:
            session.add(PlayerStats(player_id=BASE + player, fixture_id=BASE + fixture,
                                    team_id=BASE, season=SEASON, minutes=90))
    await session.flush()
    return SFAScoreRepository(session)


async def test_movement_is_computed_before_pagination_and_search():
    async with movement_session() as session:
        repo = await seed(session)
        scope = AwardPeriodScope("season-2099", "2099/2100", ScopeKind.AWARD_PERIOD,
                                 (ScoreSource(SEASON, (BASE,)),))
        rows = await repo.get_ranking_for_scope(scope, rules_version_id=BASE, use_total=True)
        assert [(r.player_id - BASE, r.rank, r.prev_rank) for r in rows] == [(3, 1, None), (2, 2, 2), (1, 3, 1)]
        assert await repo.get_ranking_total_for_scope(scope, rules_version_id=BASE, use_total=True) == 3
        page = await repo.get_ranking_for_scope(scope, rules_version_id=BASE, use_total=True, limit=1, offset=2)
        assert (page[0].rank, page[0].prev_rank) == (3, 1)
        search = await repo.get_ranking_for_scope(scope, rules_version_id=BASE, use_total=True, name="Movement 1")
        assert (search[0].rank, search[0].prev_rank) == (3, 1)


async def test_profile_sorting_has_no_points_movement():
    async with movement_session() as session:
        repo = await seed(session)
        rows = await repo.get_ranking(SEASON, rules_version_id=BASE, bonus_label="Goleador")
        assert len(rows) == 3
        assert all(row.prev_rank is None for row in rows)
