from __future__ import annotations

from typing import Protocol, runtime_checkable

from sfa.domain.ports import (
    PlayerEventRepositoryProtocol,
    PlayerSeasonStatsDTO,
    SeasonRepositoryProtocol,
)


@runtime_checkable
class GetPlayerSeasonStatsUseCaseProtocol(Protocol):
    async def execute(
        self,
        player_id: int,
        competition_id: int | None,
        season: str | None,
        scope: str | None = None,
    ) -> PlayerSeasonStatsDTO | None: ...


class GetPlayerSeasonStatsUseCase(GetPlayerSeasonStatsUseCaseProtocol):
    def __init__(
        self,
        event_repo: PlayerEventRepositoryProtocol,
        season_repo: SeasonRepositoryProtocol | None = None,
    ) -> None:
        self._event_repo = event_repo
        self._season_repo = season_repo

    async def execute(
        self, player_id: int, competition_id: int | None, season: str | None,
        scope: str | None = None,
    ) -> PlayerSeasonStatsDTO | None:
        if season is not None and scope is not None:
            raise ValueError("scope and season are mutually exclusive")
        if scope is not None:
            if self._season_repo is None:
                raise ValueError("Scope repository is not configured")
            resolved_scope = await self._season_repo.resolve_scope(scope)
            if resolved_scope is None:
                return None
            return await self._event_repo.get_player_season_stats(
                player_id, competition_id, None, resolved_scope
            )
        normalized_season = None if season == "all" else season
        return await self._event_repo.get_player_season_stats(
            player_id, competition_id, normalized_season
        )
