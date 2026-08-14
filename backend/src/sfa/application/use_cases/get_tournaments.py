from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sfa.domain.ports import (
    TournamentCompetitionDTO,
    TournamentDetailDTO,
    TournamentRepositoryProtocol,
)


@dataclass(frozen=True)
class TournamentCatalogResult:
    season: str
    competitions: tuple[TournamentCompetitionDTO, ...]


@runtime_checkable
class ListTournamentsUseCaseProtocol(Protocol):
    async def execute(self, season: str | None = None) -> TournamentCatalogResult: ...


class ListTournamentsUseCase(ListTournamentsUseCaseProtocol):
    def __init__(self, repository: TournamentRepositoryProtocol) -> None:
        self._repository = repository

    async def execute(self, season: str | None = None) -> TournamentCatalogResult:
        resolved_season = season or await self._repository.resolve_latest_season()
        if resolved_season is None:
            raise ValueError("No club tournament season found")
        competitions = await self._repository.list_competitions(resolved_season)
        return TournamentCatalogResult(
            season=resolved_season,
            competitions=tuple(competitions),
        )


@runtime_checkable
class GetTournamentUseCaseProtocol(Protocol):
    async def execute(
        self, competition_id: int, season: str | None = None,
    ) -> TournamentDetailDTO: ...


class GetTournamentUseCase(GetTournamentUseCaseProtocol):
    def __init__(self, repository: TournamentRepositoryProtocol) -> None:
        self._repository = repository

    async def execute(
        self, competition_id: int, season: str | None = None,
    ) -> TournamentDetailDTO:
        resolved_season = season or await self._repository.resolve_latest_season()
        if resolved_season is None:
            raise ValueError("No club tournament season found")
        tournament = await self._repository.get_tournament(
            competition_id,
            resolved_season,
        )
        if tournament is None:
            raise ValueError("Tournament not found for this season")
        return tournament
