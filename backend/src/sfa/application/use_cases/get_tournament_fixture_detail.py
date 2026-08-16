from __future__ import annotations

from dataclasses import replace

from sfa.domain.fixture_detail_ports import (
    FixtureDetailDTO,
    FixtureDetailRepositoryProtocol,
)
from sfa.domain.ports import TournamentRepositoryProtocol

CURRENT_CLUB_SEASON = "2026"


class GetTournamentFixtureDetailUseCase:
    def __init__(
        self,
        tournament_repository: TournamentRepositoryProtocol,
        detail_repository: FixtureDetailRepositoryProtocol,
    ) -> None:
        self._tournament_repository = tournament_repository
        self._detail_repository = detail_repository

    async def execute(
        self,
        fixture_external_id: int,
        season: str | None = None,
    ) -> FixtureDetailDTO:
        resolved_season = season or await self._tournament_repository.resolve_latest_season()
        if resolved_season != CURRENT_CLUB_SEASON:
            raise ValueError("Fixture detail is only available for the current club season")

        fixture = await self._tournament_repository.get_fixture_by_external_id(
            fixture_external_id,
            resolved_season,
        )
        if fixture is None:
            raise ValueError("Tournament fixture not found for the current season")

        detail = await self._detail_repository.get_fixture_detail(fixture_external_id)
        if detail is None:
            raise ValueError("Tournament fixture detail not found")
        events = await self._detail_repository.get_fixture_events(fixture_external_id)
        return replace(detail, events=events)
