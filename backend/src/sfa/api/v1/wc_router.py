from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from sfa.api.v1.schemas.wc_schemas import (
    WcFixtureDetailResponseSchema,
    WcFixtureSchema,
    WcFixturesResponseSchema,
    WcLineupPlayerSchema,
    WcLiveResponseSchema,
    WcStandingSchema,
    WcStandingsResponseSchema,
    WcStatisticSchema,
    WcTeamSchema,
    WcTeamLineupSchema,
    WcVenueSchema,
)
from sfa.application.use_cases.get_world_cup import (
    GetWorldCupFixtureDetailUseCase,
    GetWorldCupFixturesUseCase,
    GetWorldCupLiveUseCase,
    GetWorldCupStandingsUseCase,
    LIVE_STATUSES,
)
from sfa.core.dependencies import (
    get_world_cup_fixture_detail_use_case,
    get_world_cup_fixtures_use_case,
    get_world_cup_live_use_case,
    get_world_cup_standings_use_case,
)
from sfa.domain.world_cup_ports import (
    WorldCupFixtureDTO,
    WorldCupStandingDTO,
    WorldCupTeamLineupDTO,
)

router = APIRouter()


def _team_schema(external_id: int, name: str) -> WcTeamSchema:
    return WcTeamSchema(id=external_id, external_id=external_id, name=name)


def _fixture_schema(fixture: WorldCupFixtureDTO) -> WcFixtureSchema:
    return WcFixtureSchema(
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
        home_team=_team_schema(
            fixture.home_team.external_id,
            fixture.home_team.name,
        ),
        away_team=_team_schema(
            fixture.away_team.external_id,
            fixture.away_team.name,
        ),
    )


def _standing_schema(standing: WorldCupStandingDTO) -> WcStandingSchema:
    return WcStandingSchema(
        group=standing.group,
        position=standing.position,
        team=_team_schema(standing.team.external_id, standing.team.name),
        played=standing.played,
        won=standing.won,
        drawn=standing.drawn,
        lost=standing.lost,
        goals_for=standing.goals_for,
        goals_against=standing.goals_against,
        goal_difference=standing.goal_difference,
        points=standing.points,
        form=standing.form,
    )


def _lineup_schema(lineup: WorldCupTeamLineupDTO) -> WcTeamLineupSchema:
    return WcTeamLineupSchema(
        team=_team_schema(lineup.team.external_id, lineup.team.name),
        formation=lineup.formation,
        coach_name=lineup.coach_name,
        coach_photo=lineup.coach_photo,
        start_xi=[
            WcLineupPlayerSchema(**player.__dict__) for player in lineup.start_xi
        ],
        substitutes=[
            WcLineupPlayerSchema(**player.__dict__)
            for player in lineup.substitutes
        ],
    )


@router.get("/wc/fixtures", response_model=WcFixturesResponseSchema)
async def get_wc_fixtures(
    use_case: Annotated[
        GetWorldCupFixturesUseCase,
        Depends(get_world_cup_fixtures_use_case),
    ],
) -> WcFixturesResponseSchema:
    result = await use_case.execute()
    return WcFixturesResponseSchema(
        season=result.season,
        fixtures=[_fixture_schema(fixture) for fixture in result.fixtures],
    )


@router.get("/wc/live", response_model=WcLiveResponseSchema)
async def get_wc_live(
    use_case: Annotated[
        GetWorldCupLiveUseCase,
        Depends(get_world_cup_live_use_case),
    ],
) -> WcLiveResponseSchema:
    result = await use_case.execute()
    return WcLiveResponseSchema(
        live=[_fixture_schema(fixture) for fixture in result.live],
        has_live=result.has_live,
    )


@router.get(
    "/wc/fixtures/{fixture_id}",
    response_model=WcFixtureDetailResponseSchema,
)
async def get_wc_fixture_detail(
    fixture_id: int,
    use_case: Annotated[
        GetWorldCupFixtureDetailUseCase,
        Depends(get_world_cup_fixture_detail_use_case),
    ],
) -> WcFixtureDetailResponseSchema:
    try:
        detail = await use_case.execute(fixture_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return WcFixtureDetailResponseSchema(
        fixture=_fixture_schema(detail.fixture),
        venue=WcVenueSchema(**detail.venue.__dict__),
        referee=detail.referee,
        lineups=[_lineup_schema(lineup) for lineup in detail.lineups],
        statistics=[
            WcStatisticSchema(**statistic.__dict__)
            for statistic in detail.statistics
        ],
    )


@router.get("/wc/standings", response_model=WcStandingsResponseSchema)
async def get_wc_standings(
    use_case: Annotated[
        GetWorldCupStandingsUseCase,
        Depends(get_world_cup_standings_use_case),
    ],
) -> WcStandingsResponseSchema:
    result = await use_case.execute()
    return WcStandingsResponseSchema(
        season=result.season,
        standings=[_standing_schema(standing) for standing in result.standings],
    )
