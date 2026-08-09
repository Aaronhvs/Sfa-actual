from __future__ import annotations

from sfa.domain.individual_honors import (
    IndividualHonorRepositoryPort,
    PlayerIndividualHonorDTO,
)
from sfa.domain.ports import SeasonRepositoryProtocol, SFAScoreRepositoryProtocol


class GetPlayerIndividualHonorsUseCase:
    def __init__(
        self,
        honor_repo: IndividualHonorRepositoryPort,
        season_repo: SeasonRepositoryProtocol,
        score_repo: SFAScoreRepositoryProtocol,
        default_rules_version_id: int | None = None,
    ) -> None:
        self._honor_repo = honor_repo
        self._season_repo = season_repo
        self._score_repo = score_repo
        self._default_rules_version_id = default_rules_version_id

    async def execute(
        self,
        player_id: int,
        *,
        scope_key: str | None = None,
        all_history: bool = False,
        rules_version_id: int | None = None,
    ) -> list[PlayerIndividualHonorDTO]:
        resolved_rules_version_id = rules_version_id or self._default_rules_version_id
        if resolved_rules_version_id is None:
            return []
        if all_history:
            return await self._honor_repo.get_player_honors(
                player_id, resolved_rules_version_id
            )
        scope = await self._season_repo.resolve_scope(scope_key)
        if scope is None:
            return []
        resolved_rules_version_id = await self._score_repo.resolve_rules_version_id_for_scope(
            scope, resolved_rules_version_id
        )
        return await self._honor_repo.get_player_honors(
            player_id, resolved_rules_version_id, scope.key
        )
