from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from sfa.api.v1.schemas.ranking import RankingPaginationSchema
from sfa.api.v1.schemas.team_ranking import RankedTeamSchema, TeamRankingModelSchema, TeamRankingResponseSchema
from sfa.application.use_cases.get_team_ranking import GetTeamRankingUseCase
from sfa.core.dependencies import get_team_ranking_use_case

router = APIRouter()


@router.get("/teams/ranking", response_model=TeamRankingResponseSchema)
async def get_team_ranking(
    use_case: Annotated[GetTeamRankingUseCase, Depends(get_team_ranking_use_case)],
    season: str | None = Query(default=None, max_length=10, description="Physical starting season, e.g. 2026"),
    scope: str | None = Query(default=None, max_length=24, description="Physical season scope, e.g. season-2026"),
    participant_kind: Literal["club", "national", "national_team"] = Query(default="club"),
    competition_id: int | None = Query(default=None, ge=1),
    name: str | None = Query(default=None, max_length=150),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
) -> TeamRankingResponseSchema:
    try:
        result = await use_case.execute(
            season=season, scope=scope, participant_kind=participant_kind,
            competition_id=competition_id, name=name, page=page, limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return TeamRankingResponseSchema(
        season=result.season, scope=result.scope, total=result.total,
        pagination=RankingPaginationSchema(**asdict(result.pagination)),
        model=TeamRankingModelSchema(**asdict(result.model)),
        ranking=[RankedTeamSchema(**asdict(item)) for item in result.ranking],
    )
