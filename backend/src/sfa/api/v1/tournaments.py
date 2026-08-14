from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from sfa.api.v1.schemas.tournaments import (
    TournamentCatalogResponseSchema,
    TournamentCompetitionSchema,
    TournamentDetailResponseSchema,
)
from sfa.application.use_cases.get_tournaments import (
    GetTournamentUseCase,
    ListTournamentsUseCase,
)
from sfa.core.dependencies import (
    get_tournament_use_case,
    get_tournaments_use_case,
)

router = APIRouter()


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
