from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from sfa.api.v1.schemas.elo_schemas import (
    RecalculateEloRequest,
    RecalculateEloResponse,
    SeedClubEloRequest,
    SeedClubEloResponse,
)
from sfa.application.use_cases.calculate_elo_ratings import CalculateEloRatingsUseCase
from sfa.application.use_cases.seed_clubelo import SeedClubEloUseCase
from sfa.core.dependencies import get_calculate_elo_use_case, get_seed_clubelo_use_case

router = APIRouter(prefix="/admin/elo", tags=["elo"])


@router.post("/seed", response_model=SeedClubEloResponse)
async def seed_clubelo(
    body: SeedClubEloRequest,
    use_case: Annotated[SeedClubEloUseCase, Depends(get_seed_clubelo_use_case)],
) -> SeedClubEloResponse:
    """Download ClubElo snapshot and populate team_strengths."""
    result = await use_case.execute(date_str=body.date_str, season=body.season)
    if result.status == "failed":
        raise HTTPException(status_code=503, detail=result.error)
    return SeedClubEloResponse(
        date_str=result.date_str,
        season=result.season,
        matched=result.matched,
        unmatched=result.unmatched,
        status=result.status,
        error=result.error,
    )


@router.post("/recalculate", response_model=RecalculateEloResponse)
async def recalculate_elo(
    body: RecalculateEloRequest,
    use_case: Annotated[CalculateEloRatingsUseCase, Depends(get_calculate_elo_use_case)],
) -> RecalculateEloResponse:
    """Recalculate ELO ratings by processing fixtures in chronological order."""
    result = await use_case.execute(
        season=body.season,
        competition_ids=body.competition_ids,
        k_factors=body.k_factors,
        default_k=body.default_k,
    )
    if result.status == "failed":
        raise HTTPException(status_code=500, detail=result.error)
    return RecalculateEloResponse(
        season=result.season,
        fixtures_processed=result.fixtures_processed,
        teams_updated=result.teams_updated,
        status=result.status,
        error=result.error,
    )
