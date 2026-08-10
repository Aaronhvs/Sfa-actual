from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.compare_players import ComparePlayersUseCase
from sfa.application.use_cases.get_player_detail import (
    PlayerDetailResult,
    PlayerNotFoundError,
)
from sfa.domain.ports import PlayerEventDTO, PlayerFixtureDTO, PlayerSeasonStatsDTO


def _detail(player_id: int, name: str) -> PlayerDetailResult:
    return PlayerDetailResult(
        id=player_id,
        name=name,
        team="Team A",
        position="DEL",
        competition="Liga",
        sfa_pts=1000.0,
        matches=20,
        total_goals=10,
        total_assists=5,
        photo_url=None,
        global_rank=1,
        season="2025",
        breakdown=None,
        competitions=["Liga"],
    )


def _stats(player_id: int) -> PlayerSeasonStatsDTO:
    return PlayerSeasonStatsDTO(
        player_id=player_id,
        competition_id=None,
        season="season-2025",
        matches=20,
        minutes=1600,
        goals=10,
        assists=5,
        shots_total=50,
        shots_on=30,
        passes_total=700,
        passes_accuracy_avg=87.5,
        passes_key=30,
        dribbles_won=40,
        dribbles_attempts=70,
        dribbles_past=8,
        duels_won=90,
        duels_total=150,
        tackles_won=20,
        interceptions=12,
        blocks=3,
        fouls_drawn=35,
        fouls_committed=18,
        cards_yellow=3,
        cards_red=0,
        penalty_won=2,
        saves=0,
        goals_conceded=0,
        rating_avg=7.42,
        dribble_success_rate=0.571,
        duel_win_rate=0.6,
    )


def _event(player_id: int) -> PlayerEventDTO:
    return PlayerEventDTO(
        id=player_id,
        competition="Liga",
        stage="regular",
        fixture_id=10,
        home_team="Team A",
        away_team="Team B",
        played_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        minute=78,
        event_type="goal",
        score_before="1-1",
        score_diff=0,
        m1=1.2,
        m2=1.0,
        m3=1.8,
        m4=1.0,
        mvisit=1.0,
        pts=1500.0,
    )


def _fixture() -> PlayerFixtureDTO:
    return PlayerFixtureDTO(
        fixture_id=10,
        competition="Liga",
        stage="regular",
        home_team="Team A",
        away_team="Team B",
        played_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        sfa_pts=1800.0,
        events_count=2,
    )


class FakeDetailUseCase:
    def __init__(self, details: dict[int, PlayerDetailResult]):
        self.details = details
        self.calls: list[tuple[int, str | None, str | None]] = []

    async def execute(
        self,
        player_id: int,
        season: str | None = None,
        scope: str | None = None,
        rules_version_id: int | None = None,
    ) -> PlayerDetailResult:
        self.calls.append((player_id, season, scope))
        detail = self.details.get(player_id)
        if detail is None:
            raise PlayerNotFoundError(player_id)
        if scope is not None:
            return replace(detail, scope=scope)
        if season is None:
            return replace(detail, scope="season-2025")
        return replace(detail, season=season)


class FakeEventsUseCase:
    def __init__(self):
        self.calls: list[tuple[int, str | None, str | None]] = []

    async def execute(self, player_id: int, season=None, scope=None, **kwargs):
        self.calls.append((player_id, season, scope))
        return [_event(player_id)]


class FakeFixturesUseCase:
    def __init__(self):
        self.calls: list[tuple[int, str | None, str | None, bool]] = []

    async def execute(
        self,
        player_id: int,
        season=None,
        scope=None,
        include_breakdown=True,
        **kwargs,
    ):
        self.calls.append((player_id, season, scope, include_breakdown))
        return [_fixture()]


class FakeStatsUseCase:
    def __init__(self):
        self.calls: list[tuple[int, str | None, str | None]] = []

    async def execute(self, player_id: int, competition_id, season, scope=None):
        self.calls.append((player_id, season, scope))
        return _stats(player_id)


def _use_case(details: dict[int, PlayerDetailResult]):
    detail_uc = FakeDetailUseCase(details)
    events_uc = FakeEventsUseCase()
    fixtures_uc = FakeFixturesUseCase()
    stats_uc = FakeStatsUseCase()
    use_case = ComparePlayersUseCase(
        detail_uc=detail_uc,
        events_uc=events_uc,
        fixtures_uc=fixtures_uc,
        stats_uc=stats_uc,
    )
    return use_case, detail_uc, events_uc, fixtures_uc, stats_uc


@pytest.mark.anyio
async def test_compare_returns_complete_analytics_for_both_players():
    use_case, _, _, fixtures_uc, _ = _use_case(
        {1: _detail(1, "Messi"), 2: _detail(2, "Ronaldo")}
    )

    result = await use_case.execute(1, 2, scope="season-2025")

    assert result.player_a.name == "Messi"
    assert result.player_b.name == "Ronaldo"
    assert result.scope == "season-2025"
    assert result.player_a_analytics.stats.shots_total == 50
    assert result.player_b_analytics.events[0].minute == 78
    assert result.player_a_analytics.fixtures[0].sfa_pts == 1800.0
    assert all(call[3] is False for call in fixtures_uc.calls)


@pytest.mark.anyio
async def test_default_scope_from_player_a_is_reused_everywhere():
    use_case, detail_uc, events_uc, _, stats_uc = _use_case(
        {1: _detail(1, "Messi"), 2: _detail(2, "Ronaldo")}
    )

    result = await use_case.execute(1, 2)

    assert result.scope == "season-2025"
    assert detail_uc.calls[1] == (2, None, "season-2025")
    assert events_uc.calls == [
        (1, None, "season-2025"),
        (2, None, "season-2025"),
    ]
    assert stats_uc.calls == [
        (1, None, "season-2025"),
        (2, None, "season-2025"),
    ]


@pytest.mark.anyio
async def test_raises_when_player_a_not_found():
    use_case, *_ = _use_case({2: _detail(2, "Ronaldo")})

    with pytest.raises(PlayerNotFoundError):
        await use_case.execute(999, 2, season="2025")


@pytest.mark.anyio
async def test_raises_when_player_b_not_found():
    use_case, *_ = _use_case({1: _detail(1, "Messi")})

    with pytest.raises(PlayerNotFoundError):
        await use_case.execute(1, 999, season="2025")


@pytest.mark.anyio
async def test_rejects_same_player():
    use_case, *_ = _use_case({1: _detail(1, "Messi")})

    with pytest.raises(ValueError, match="different"):
        await use_case.execute(1, 1, season="2025")


@pytest.mark.anyio
async def test_rejects_season_and_scope_together():
    use_case, *_ = _use_case(
        {1: _detail(1, "Messi"), 2: _detail(2, "Ronaldo")}
    )

    with pytest.raises(ValueError, match="mutually exclusive"):
        await use_case.execute(1, 2, season="2025", scope="season-2025")
