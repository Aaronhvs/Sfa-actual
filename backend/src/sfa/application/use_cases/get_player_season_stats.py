from __future__ import annotations

from typing import Protocol, runtime_checkable

from sfa.domain.ports import PlayerEventRepositoryProtocol, PlayerSeasonStatsDTO


@runtime_checkable
class GetPlayerSeasonStatsUseCaseProtocol(Protocol):
    async def execute(
        self, player_id: int, competition_id: int | None, season: str,
    ) -> PlayerSeasonStatsDTO | None: ...


class GetPlayerSeasonStatsUseCase(GetPlayerSeasonStatsUseCaseProtocol):
    def __init__(self, event_repo: PlayerEventRepositoryProtocol) -> None:
        self._event_repo = event_repo

    async def execute(
        self, player_id: int, competition_id: int | None, season: str,
    ) -> PlayerSeasonStatsDTO | None:
        normalized_season = None if season == "all" else season
        return await self._event_repo.get_player_season_stats(
            player_id, competition_id, normalized_season
        )
