from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, Protocol, runtime_checkable

from sfa.domain.ports import (
    TournamentCompetitionDTO,
    TournamentDashboardDTO,
    TournamentDetailDTO,
    TournamentRepositoryProtocol,
)


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


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


@runtime_checkable
class GetTournamentDashboardUseCaseProtocol(Protocol):
    async def execute(
        self,
        season: str | None = None,
        fixture_date: date | None = None,
    ) -> TournamentDashboardDTO: ...


class GetTournamentDashboardUseCase(GetTournamentDashboardUseCaseProtocol):
    def __init__(
        self,
        repository: TournamentRepositoryProtocol,
        today_provider: Callable[[], date] = _utc_today,
    ) -> None:
        self._repository = repository
        self._today_provider = today_provider

    async def execute(
        self,
        season: str | None = None,
        fixture_date: date | None = None,
    ) -> TournamentDashboardDTO:
        resolved_season = season or await self._repository.resolve_latest_season()
        if resolved_season is None:
            raise ValueError("No club tournament season found")

        available_dates = sorted(
            set(await self._repository.list_fixture_dates(resolved_season))
        )
        selected_date = fixture_date
        if selected_date is None and available_dates:
            today = self._today_provider()
            selected_date = next(
                (item for item in available_dates if item >= today),
                available_dates[-1],
            )

        previous_date = None
        next_date = None
        groups = ()
        if selected_date is not None:
            previous_date = next(
                (item for item in reversed(available_dates) if item < selected_date),
                None,
            )
            next_date = next(
                (item for item in available_dates if item > selected_date),
                None,
            )
            groups = tuple(
                await self._repository.get_fixture_groups(
                    resolved_season,
                    selected_date,
                )
            )

        return TournamentDashboardDTO(
            season=resolved_season,
            selected_date=selected_date,
            previous_date=previous_date,
            next_date=next_date,
            groups=groups,
        )
