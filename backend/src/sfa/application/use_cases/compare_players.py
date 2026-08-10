from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sfa.application.use_cases.get_player_detail import (
    GetPlayerDetailUseCaseProtocol,
    PlayerDetailResult,
)
from sfa.application.use_cases.get_player_events import GetPlayerEventsUseCaseProtocol
from sfa.application.use_cases.get_player_fixtures import GetPlayerFixturesUseCaseProtocol
from sfa.application.use_cases.get_player_season_stats import (
    GetPlayerSeasonStatsUseCaseProtocol,
)
from sfa.domain.ports import PlayerEventDTO, PlayerFixtureDTO, PlayerSeasonStatsDTO


@dataclass(frozen=True)
class ComparePlayerAnalytics:
    stats: PlayerSeasonStatsDTO | None
    events: tuple[PlayerEventDTO, ...]
    fixtures: tuple[PlayerFixtureDTO, ...]


@dataclass(frozen=True)
class CompareResult:
    season: str
    scope: str | None
    player_a: PlayerDetailResult
    player_b: PlayerDetailResult
    player_a_analytics: ComparePlayerAnalytics
    player_b_analytics: ComparePlayerAnalytics


@runtime_checkable
class ComparePlayersUseCaseProtocol(Protocol):
    async def execute(
        self,
        player_a_id: int,
        player_b_id: int,
        season: str | None = None,
        scope: str | None = None,
    ) -> CompareResult: ...


class ComparePlayersUseCase(ComparePlayersUseCaseProtocol):
    def __init__(
        self,
        detail_uc: GetPlayerDetailUseCaseProtocol,
        events_uc: GetPlayerEventsUseCaseProtocol,
        fixtures_uc: GetPlayerFixturesUseCaseProtocol,
        stats_uc: GetPlayerSeasonStatsUseCaseProtocol,
    ) -> None:
        self._detail_uc = detail_uc
        self._events_uc = events_uc
        self._fixtures_uc = fixtures_uc
        self._stats_uc = stats_uc

    async def execute(
        self,
        player_a_id: int,
        player_b_id: int,
        season: str | None = None,
        scope: str | None = None,
    ) -> CompareResult:
        if season is not None and scope is not None:
            raise ValueError("scope and season are mutually exclusive")
        if player_a_id == player_b_id:
            raise ValueError("players must be different")

        detail_a = await self._detail_uc.execute(player_a_id, season, scope)
        resolved_scope = scope
        resolved_season = season
        if season is None and scope is None:
            resolved_scope = detail_a.scope
            if resolved_scope is None:
                resolved_season = detail_a.season

        detail_b = await self._detail_uc.execute(
            player_b_id,
            resolved_season,
            resolved_scope,
        )
        analytics_a = await self._get_analytics(
            player_a_id, resolved_season, resolved_scope
        )
        analytics_b = await self._get_analytics(
            player_b_id, resolved_season, resolved_scope
        )

        return CompareResult(
            season=detail_a.season or detail_b.season,
            scope=resolved_scope,
            player_a=detail_a,
            player_b=detail_b,
            player_a_analytics=analytics_a,
            player_b_analytics=analytics_b,
        )

    async def _get_analytics(
        self,
        player_id: int,
        season: str | None,
        scope: str | None,
    ) -> ComparePlayerAnalytics:
        stats = await self._stats_uc.execute(player_id, None, season, scope)
        events = await self._events_uc.execute(
            player_id,
            season=season,
            scope=scope,
        )
        fixtures = await self._fixtures_uc.execute(
            player_id,
            season=season,
            include_breakdown=False,
            scope=scope,
        )
        return ComparePlayerAnalytics(
            stats=stats,
            events=tuple(events),
            fixtures=tuple(fixtures),
        )
