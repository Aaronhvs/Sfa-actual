from __future__ import annotations

from dataclasses import replace

from sfa.domain.fixture_detail_ports import (
    FixtureDetailDTO,
    FixtureDetailRepositoryProtocol,
    FixtureSummaryDTO,
    FixtureTeamDTO,
    FixtureVenueDTO,
)
from sfa.domain.ports import TournamentFixtureDTO, TournamentRepositoryProtocol

CURRENT_CLUB_SEASON = "2026"

LIVE_STATUSES = {"1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT", "LIVE"}

STATUS_LABELS = {
    "NS": "Programado",
    "TBD": "Por definir",
    "1H": "Primer tiempo",
    "HT": "Descanso",
    "2H": "Segundo tiempo",
    "ET": "Prorroga",
    "BT": "Pausa",
    "P": "Penaltis",
    "LIVE": "En vivo",
    "INT": "Interrumpido",
    "SUSP": "Suspendido",
    "FT": "Finalizado",
    "AET": "Finalizado tras prorroga",
    "PEN": "Finalizado tras penaltis",
    "PST": "Aplazado",
    "CANC": "Cancelado",
    "ABD": "Abandonado",
    "AWD": "Victoria administrativa",
    "WO": "Walkover",
}


def _canonical_summary(
    fixture: TournamentFixtureDTO,
    external: FixtureSummaryDTO | None,
) -> FixtureSummaryDTO:
    statuses_match = external is not None and fixture.status == external.status
    is_live = fixture.status in LIVE_STATUSES
    return FixtureSummaryDTO(
        external_id=fixture.external_id,
        stage=fixture.stage,
        matchday=fixture.matchday,
        played_at=fixture.played_at,
        status=fixture.status,
        status_label=STATUS_LABELS.get(fixture.status, fixture.status),
        elapsed=(
            external.elapsed
            if external is not None and statuses_match and is_live
            else None
        ),
        home_team=FixtureTeamDTO(
            external_id=fixture.home_team.external_id or fixture.home_team.id,
            name=fixture.home_team.name,
        ),
        away_team=FixtureTeamDTO(
            external_id=fixture.away_team.external_id or fixture.away_team.id,
            name=fixture.away_team.name,
        ),
        home_goals=fixture.home_goals,
        away_goals=fixture.away_goals,
        home_winner=(external.home_winner if external and statuses_match else None),
        away_winner=(external.away_winner if external and statuses_match else None),
        competition_id=fixture.competition_id,
        competition_name=fixture.competition_name,
    )


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
            detail = FixtureDetailDTO(
                fixture=_canonical_summary(fixture, None),
                venue=FixtureVenueDTO(name=None, city=None),
                referee=None,
                lineups=[],
                statistics=[],
            )
        events = await self._detail_repository.get_fixture_events(fixture_external_id)
        momentum = await self._detail_repository.get_fixture_sfa_momentum(
            fixture.id,
            fixture.home_team.id,
            fixture.away_team.id,
        )
        return replace(
            detail,
            fixture=_canonical_summary(fixture, detail.fixture),
            events=events,
            sfa_momentum=momentum,
        )
