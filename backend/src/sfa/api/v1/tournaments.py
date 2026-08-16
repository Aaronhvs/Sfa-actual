from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from sfa.api.v1.schemas.tournaments import (
    TournamentCatalogResponseSchema,
    TournamentCompetitionSchema,
    TournamentDashboardResponseSchema,
    TournamentDetailResponseSchema,
    TournamentMatchDetailResponseSchema,
    TournamentMatchEventSchema,
    TournamentMatchFixtureSchema,
    TournamentMatchLineupPlayerSchema,
    TournamentMatchStatisticSchema,
    TournamentMatchTeamLineupSchema,
    TournamentMatchTeamSchema,
    TournamentMatchVenueSchema,
)
from sfa.application.use_cases.get_tournament_fixture_detail import (
    GetTournamentFixtureDetailUseCase,
)
from sfa.application.use_cases.get_tournaments import (
    GetTournamentDashboardUseCase,
    GetTournamentUseCase,
    ListTournamentsUseCase,
)
from sfa.core.dependencies import (
    get_tournament_dashboard_use_case,
    get_tournament_fixture_detail_use_case,
    get_tournament_use_case,
    get_tournaments_use_case,
)

router = APIRouter()

LIVE_STATUSES = {"1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT", "LIVE"}


def _match_team_schema(external_id: int, name: str) -> TournamentMatchTeamSchema:
    return TournamentMatchTeamSchema(
        id=external_id,
        external_id=external_id,
        name=name,
    )


def _match_fixture_schema(fixture) -> TournamentMatchFixtureSchema:
    return TournamentMatchFixtureSchema(
        id=fixture.external_id,
        external_id=fixture.external_id,
        stage=fixture.stage,
        matchday=fixture.matchday,
        played_at=fixture.played_at,
        is_live=fixture.status in LIVE_STATUSES,
        status=fixture.status,
        status_label=fixture.status_label,
        elapsed=fixture.elapsed,
        home_goals=fixture.home_goals,
        away_goals=fixture.away_goals,
        home_winner=fixture.home_winner,
        away_winner=fixture.away_winner,
        home_team=_match_team_schema(
            fixture.home_team.external_id,
            fixture.home_team.name,
        ),
        away_team=_match_team_schema(
            fixture.away_team.external_id,
            fixture.away_team.name,
        ),
    )


def _match_lineup_schema(lineup) -> TournamentMatchTeamLineupSchema:
    return TournamentMatchTeamLineupSchema(
        team=_match_team_schema(lineup.team.external_id, lineup.team.name),
        formation=lineup.formation,
        coach_name=lineup.coach_name,
        coach_photo=lineup.coach_photo,
        start_xi=[
            TournamentMatchLineupPlayerSchema(**player.__dict__)
            for player in lineup.start_xi
        ],
        substitutes=[
            TournamentMatchLineupPlayerSchema(**player.__dict__)
            for player in lineup.substitutes
        ],
    )


@router.get("/tournaments", response_model=TournamentCatalogResponseSchema)
async def list_tournaments(
    use_case: Annotated[
        ListTournamentsUseCase,
        Depends(get_tournaments_use_case),
    ],
    season: str | None = Query(default=None),
) -> TournamentCatalogResponseSchema:
    try:
        result = await use_case.execute(season)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TournamentCatalogResponseSchema(
        season=result.season,
        competitions=[
            TournamentCompetitionSchema.model_validate(item)
            for item in result.competitions
        ],
    )


@router.get(
    "/tournaments/dashboard",
    response_model=TournamentDashboardResponseSchema,
)
async def get_tournament_dashboard(
    use_case: Annotated[
        GetTournamentDashboardUseCase,
        Depends(get_tournament_dashboard_use_case),
    ],
    season: str | None = Query(default=None),
    fixture_date: date | None = Query(default=None, alias="date"),
) -> TournamentDashboardResponseSchema:
    try:
        result = await use_case.execute(season, fixture_date)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TournamentDashboardResponseSchema.model_validate(result)


@router.get(
    "/tournaments/fixtures/{fixture_external_id}",
    response_model=TournamentMatchDetailResponseSchema,
)
async def get_tournament_fixture_detail(
    fixture_external_id: int,
    use_case: Annotated[
        GetTournamentFixtureDetailUseCase,
        Depends(get_tournament_fixture_detail_use_case),
    ],
    season: str | None = Query(default=None),
) -> TournamentMatchDetailResponseSchema:
    try:
        detail = await use_case.execute(fixture_external_id, season)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return TournamentMatchDetailResponseSchema(
        fixture=_match_fixture_schema(detail.fixture),
        venue=TournamentMatchVenueSchema(**detail.venue.__dict__),
        referee=detail.referee,
        lineups=[_match_lineup_schema(lineup) for lineup in detail.lineups],
        statistics=[
            TournamentMatchStatisticSchema(**item.__dict__)
            for item in detail.statistics
        ],
        events=[
            TournamentMatchEventSchema(**event.__dict__)
            for event in detail.events
        ],
    )


@router.get(
    "/tournaments/{competition_id}",
    response_model=TournamentDetailResponseSchema,
)
async def get_tournament(
    competition_id: int,
    use_case: Annotated[
        GetTournamentUseCase,
        Depends(get_tournament_use_case),
    ],
    season: str | None = Query(default=None),
) -> TournamentDetailResponseSchema:
    try:
        result = await use_case.execute(competition_id, season)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TournamentDetailResponseSchema.model_validate(result)
