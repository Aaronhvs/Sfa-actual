from typing import Annotated

from fastapi import APIRouter, Depends

from sfa.api.v1.schemas.seasons import SeasonSchema, SeasonsResponseSchema
from sfa.application.use_cases.get_seasons import GetSeasonsUseCase
from sfa.core.dependencies import get_seasons_use_case

router = APIRouter()


@router.get("/seasons", response_model=SeasonsResponseSchema)
async def get_seasons(
    use_case: Annotated[GetSeasonsUseCase, Depends(get_seasons_use_case)],
) -> SeasonsResponseSchema:
    result = await use_case.execute()
    return SeasonsResponseSchema(
        seasons=[
            SeasonSchema(season=season.season, is_latest=season.is_latest)
            for season in result.seasons
        ]
    )
