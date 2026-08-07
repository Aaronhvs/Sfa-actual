from __future__ import annotations

from typing import Protocol, runtime_checkable

from sfa.domain.ports import (
    PlayerEventDTO,
    PlayerEventRepositoryProtocol,
    SeasonRepositoryProtocol,
    SFAScoreRepositoryProtocol,
)


@runtime_checkable
class GetPlayerEventsUseCaseProtocol(Protocol):
    async def execute(
        self,
        player_id: int,
        season: str | None = None,
        competition_id: int | None = None,
    ) -> list[PlayerEventDTO]: ...


class GetPlayerEventsUseCase(GetPlayerEventsUseCaseProtocol):
    def __init__(
        self,
        event_repo: PlayerEventRepositoryProtocol,
        season_repo: SeasonRepositoryProtocol | None = None,
        score_repo: SFAScoreRepositoryProtocol | None = None,
    ) -> None:
        self._event_repo = event_repo
        self._season_repo = season_repo
        self._score_repo = score_repo

    async def execute(
        self,
        player_id: int,
        season: str | None = None,
        competition_id: int | None = None,
        rules_version_id: int | None = None,
        scope: str | None = None,
    ) -> list[PlayerEventDTO]:
        if season is not None and scope is not None:
            raise ValueError("scope and season are mutually exclusive")
        if scope is not None:
            if self._season_repo is None or self._score_repo is None:
                raise ValueError("Scope repositories are not configured")
            resolved_scope = await self._season_repo.resolve_scope(scope)
            if resolved_scope is None:
                return []
            rules_version_id = await self._score_repo.resolve_rules_version_id_for_scope(
                resolved_scope, rules_version_id
            )
            return await self._event_repo.get_events_by_player(
                player_id,
                None,
                competition_id,
                rules_version_id,
                resolved_scope,
            )
        if season == "all":
            season = None
        if rules_version_id is None:
            return await self._event_repo.get_events_by_player(
                player_id, season, competition_id,
            )
        return await self._event_repo.get_events_by_player(
            player_id, season, competition_id, rules_version_id,
        )
