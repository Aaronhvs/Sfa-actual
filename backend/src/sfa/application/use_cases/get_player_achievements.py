from __future__ import annotations

from typing import Protocol, runtime_checkable

from sfa.domain.ports import SeasonRepositoryProtocol, SFAScoreRepositoryProtocol
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
        season_repository: SeasonRepositoryProtocol | None = None,
        score_repository: SFAScoreRepositoryProtocol | None = None,
    ) -> None:
        self._repository = repository
        self._default_rules_version_id = default_rules_version_id
        self._season_repository = season_repository
        self._score_repository = score_repository

    async def execute(
        self,
        player_id: int,
        season: str | None = None,
        rules_version_id: int | None = None,
        scope: str | None = None,
    ) -> list[PlayerCompetitionAchievementDTO]:
        if season is not None and scope is not None:
            raise ValueError("scope and season are mutually exclusive")
        resolved_rules_version_id = (
            rules_version_id
            if rules_version_id is not None
            else self._default_rules_version_id
        )
        if resolved_rules_version_id is None:
            return []

        if scope is not None:
            if self._season_repository is None or self._score_repository is None:
                raise ValueError("Scope repositories are not configured")
            resolved_scope = await self._season_repository.resolve_scope(scope)
            if resolved_scope is None:
                return []
            resolved_rules_version_id = await self._score_repository.resolve_rules_version_id_for_scope(
                resolved_scope, resolved_rules_version_id
            )
            return await self._repository.get_player_achievements(
                player_id,
                resolved_rules_version_id,
                scope=resolved_scope,
            )

        normalized_season = None if season == "all" else season
        return await self._repository.get_player_achievements(
            player_id,
            resolved_rules_version_id,
            normalized_season,
        )
