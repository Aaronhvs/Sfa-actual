import dataclasses
import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from sfa.api.v1.schemas.players import (
    BreakdownEntrySchema,
    PlayerDetailSchema,
    PlayerEventSchema,
    PlayerFixtureSchema,
    PlayerCompetitionAchievementSchema,
    PlayerSeasonStatsSchema,
)
from sfa.application.use_cases.get_player_achievements import GetPlayerAchievementsUseCase
from sfa.application.use_cases.get_player_detail import (
    GetPlayerDetailUseCase,
    PlayerNotFoundError,
)
from sfa.application.use_cases.get_player_events import GetPlayerEventsUseCase
from sfa.application.use_cases.get_player_fixtures import GetPlayerFixturesUseCase
from sfa.application.use_cases.get_player_season_stats import GetPlayerSeasonStatsUseCase
from sfa.core.dependencies import (
    get_player_detail_use_case,
    get_player_achievements_use_case,
    get_player_events_use_case,
    get_player_fixtures_use_case,
    get_player_season_stats_use_case,
)

router = APIRouter()


@router.get("/players/{player_id}", response_model=PlayerDetailSchema)
async def get_player(
    player_id: int,
    use_case: Annotated[GetPlayerDetailUseCase, Depends(get_player_detail_use_case)],
    season: str | None = Query(default=None),
    rules_version_id: int | None = Query(default=None),
):
    try:
        result = await use_case.execute(player_id, season, rules_version_id)
    except PlayerNotFoundError:
        raise HTTPException(status_code=404, detail="Player not found")

    position = result.position
    if hasattr(position, "value"):
        position = position.value

    return PlayerDetailSchema(
        id=result.id,
        name=result.name,
        team=result.team,
        position=position,
        competition=result.competition,
        sfa_pts=result.sfa_pts,
        matches=result.matches,
        total_goals=result.total_goals,
        total_assists=result.total_assists,
        photo_url=result.photo_url,
        global_rank=result.global_rank,
        season=result.season,
        breakdown={
            k: BreakdownEntrySchema(count=v.count, pts=v.pts, pct=v.pct)
            for k, v in result.breakdown.items()
        } if result.breakdown else None,
        competitions=result.competitions,
        available_seasons=result.available_seasons,
    )


@router.get("/players/{player_id}/events", response_model=list[PlayerEventSchema])
async def get_player_events(
    player_id: int,
    use_case: Annotated[GetPlayerEventsUseCase, Depends(get_player_events_use_case)],
    season: str | None = Query(default=None),
    competition_id: int | None = Query(default=None),
):
    events = await use_case.execute(player_id, season, competition_id)
    return [PlayerEventSchema(**e.__dict__) for e in events]


@router.get("/players/{player_id}/stats", response_model=PlayerSeasonStatsSchema)
async def get_player_season_stats(
    player_id: int,
    use_case: Annotated[GetPlayerSeasonStatsUseCase, Depends(get_player_season_stats_use_case)],
    competition_id: int | None = Query(default=None),
    season: str = Query(...),
):
    result = await use_case.execute(player_id, competition_id, season)
    if result is None:
        raise HTTPException(status_code=404, detail="No stats found for this player/competition/season")
    return PlayerSeasonStatsSchema(**dataclasses.asdict(result))


@router.get(
    "/players/{player_id}/achievements",
    response_model=list[PlayerCompetitionAchievementSchema],
)
async def get_player_achievements(
    player_id: int,
    use_case: Annotated[
        GetPlayerAchievementsUseCase,
        Depends(get_player_achievements_use_case),
    ],
    season: str | None = Query(default=None),
    rules_version_id: int | None = Query(default=None),
):
    achievements = await use_case.execute(player_id, season, rules_version_id)
    return [
        PlayerCompetitionAchievementSchema(**dataclasses.asdict(achievement))
        for achievement in achievements
    ]


@router.get("/players/{player_id}/fixtures", response_model=list[PlayerFixtureSchema])
async def get_player_fixtures(
    player_id: int,
    use_case: Annotated[GetPlayerFixturesUseCase, Depends(get_player_fixtures_use_case)],
    season: str | None = Query(default=None),
    competition_id: int | None = Query(default=None),
    include_breakdown: bool = Query(default=True),
    competition_name: str | None = Query(default=None),
    rival: str | None = Query(default=None),
    date: datetime.date | None = Query(default=None),
):
    fixtures = await use_case.execute(
        player_id,
        season,
        competition_id,
        include_breakdown=include_breakdown,
        competition_name=competition_name,
        rival=rival,
        date=date,
    )
    return [
        PlayerFixtureSchema(
            fixture_id=f.fixture_id,
            competition=f.competition,
            stage=f.stage,
            home_team=f.home_team,
            away_team=f.away_team,
            played_at=f.played_at,
            sfa_pts=f.sfa_pts,
            events_count=f.events_count,
            minutes=f.minutes,
            shots_on=f.shots_on,
            dribbles_won=f.dribbles_won,
            duels_won=f.duels_won,
            tackles_won=f.tackles_won,
            interceptions=f.interceptions,
            blocks=f.blocks,
            fouls_drawn=f.fouls_drawn,
            home_team_logo=f.home_team_logo,
            away_team_logo=f.away_team_logo,
            rating=f.rating,
            breakdown={
                k: BreakdownEntrySchema(count=v.count, pts=v.pts, pct=None)
                for k, v in f.breakdown.items()
            } if f.breakdown else None,
        )
        for f in fixtures
    ]
