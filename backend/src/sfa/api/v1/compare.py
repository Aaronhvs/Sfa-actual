import dataclasses
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from sfa.api.v1.schemas.compare import (
    ComparePlayerAnalyticsSchema,
    CompareResponseSchema,
)
from sfa.api.v1.schemas.players import (
    BreakdownEntrySchema,
    PlayerDetailSchema,
    PlayerEventSchema,
    PlayerFixtureSchema,
    PlayerSeasonStatsSchema,
)
from sfa.application.use_cases.compare_players import (
    ComparePlayerAnalytics,
    ComparePlayersUseCase,
)
from sfa.application.use_cases.get_player_detail import PlayerNotFoundError
from sfa.core.dependencies import get_compare_players_use_case
from sfa.domain.season_scope import (
    InconsistentScopeRulesVersionError,
    ScopeNotFoundError,
)

router = APIRouter()


def _detail_to_schema(r) -> PlayerDetailSchema:
    return PlayerDetailSchema(
        id=r.id,
        name=r.name,
        team=r.team,
        position=r.position,
        competition=r.competition,
        sfa_pts=r.sfa_pts,
        matches=r.matches,
        total_goals=r.total_goals,
        total_assists=r.total_assists,
        photo_url=r.photo_url,
        global_rank=r.global_rank,
        season=r.season,
        breakdown={
            k: BreakdownEntrySchema(count=v.count, pts=v.pts)
            for k, v in r.breakdown.items()
        } if r.breakdown else None,
        competitions=r.competitions,
        available_seasons=r.available_seasons,
        scope=r.scope,
        available_scopes=r.available_scopes,
        b1_bonus_pts=r.b1_bonus_pts,
        b1_bonus_label=r.b1_bonus_label,
    )


def _analytics_to_schema(r: ComparePlayerAnalytics) -> ComparePlayerAnalyticsSchema:
    return ComparePlayerAnalyticsSchema(
        stats=(
            PlayerSeasonStatsSchema(**dataclasses.asdict(r.stats))
            if r.stats is not None else None
        ),
        events=[PlayerEventSchema(**dataclasses.asdict(event)) for event in r.events],
        fixtures=[
            PlayerFixtureSchema(**dataclasses.asdict(fixture))
            for fixture in r.fixtures
        ],
    )


@router.get("/compare", response_model=CompareResponseSchema)
async def compare_players(
    use_case: Annotated[ComparePlayersUseCase, Depends(get_compare_players_use_case)],
    player_a: int = Query(..., description="ID del primer jugador"),
    player_b: int = Query(..., description="ID del segundo jugador"),
    season: str | None = Query(default=None),
    scope: str | None = Query(default=None),
):
    if season is not None and scope is not None:
        raise HTTPException(status_code=422, detail="scope and season are mutually exclusive")
    try:
        result = await use_case.execute(player_a, player_b, season, scope)
    except PlayerNotFoundError:
        raise HTTPException(status_code=404, detail="Player not found")
    except (ScopeNotFoundError, InconsistentScopeRulesVersionError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return CompareResponseSchema(
        season=result.season,
        scope=result.scope,
        player_a=_detail_to_schema(result.player_a),
        player_b=_detail_to_schema(result.player_b),
        player_a_analytics=_analytics_to_schema(result.player_a_analytics),
        player_b_analytics=_analytics_to_schema(result.player_b_analytics),
    )
