from __future__ import annotations

from typing import Protocol, runtime_checkable

from sfa.domain.scoring_ports import (
    CompetitionAchievementRepositoryPort,
    PlayerCompetitionAchievementDTO,
)


@runtime_checkable
class GetPlayerAchievementsUseCaseProtocol(Protocol):
    async def execute(
        self,
        player_id: int,
        season: str | None = None,
        rules_version_id: int | None = None,
    ) -> list[PlayerCompetitionAchievementDTO]: ...


class GetPlayerAchievementsUseCase(GetPlayerAchievementsUseCaseProtocol):
    def __init__(
        self,
        repository: CompetitionAchievementRepositoryPort,
        default_rules_version_id: int | None = None,
    ) -> None:
        self._repository = repository
        self._default_rules_version_id = default_rules_version_id

    async def execute(
        self,
        player_id: int,
        season: str | None = None,
        rules_version_id: int | None = None,
    ) -> list[PlayerCompetitionAchievementDTO]:
        resolved_rules_version_id = (
            rules_version_id
            if rules_version_id is not None
            else self._default_rules_version_id
        )
        if resolved_rules_version_id is None:
            return []

        normalized_season = None if season == "all" else season
        return await self._repository.get_player_achievements(
            player_id,
            resolved_rules_version_id,
            normalized_season,
        )
