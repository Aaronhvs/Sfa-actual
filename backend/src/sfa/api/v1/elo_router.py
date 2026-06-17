from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from sfa.api.v1.schemas.elo_schemas import (
    ManualNationalTeamEloSchema,
    NationalTeamEloCoverageResponse,
    NationalTeamEloCoverageRowSchema,
    RecalculateEloRequest,
    RecalculateEloResponse,
    SeedClubEloRequest,
    SeedClubEloResponse,
    SeedNationalTeamEloRequest,
    SeedNationalTeamEloResponse,
)
from sfa.application.use_cases.calculate_elo_ratings import CalculateEloRatingsUseCase
from sfa.application.use_cases.get_national_team_elo_coverage import (
    GetNationalTeamEloCoverageUseCase,
)
from sfa.application.use_cases.seed_clubelo import SeedClubEloUseCase
from sfa.application.use_cases.seed_national_team_elo import SeedNationalTeamEloUseCase
from sfa.core.dependencies import (
    get_calculate_elo_use_case,
    get_national_team_elo_coverage_use_case,
    get_seed_clubelo_use_case,
    get_seed_national_team_elo_use_case,
    require_admin_key,
)
from sfa.domain.scoring_ports import NationalTeamEloEntry

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


@router.post(
    "/national-teams/seed",
    response_model=SeedNationalTeamEloResponse,
    dependencies=[Depends(require_admin_key)],
)
async def seed_national_team_elo(
    body: SeedNationalTeamEloRequest,
    use_case: Annotated[
        SeedNationalTeamEloUseCase,
        Depends(get_seed_national_team_elo_use_case),
    ],
) -> SeedNationalTeamEloResponse:
    """Seed World Cup team strengths from national-team ELO ratings."""
    result = await use_case.execute(
        season=body.season,
        competition_id=body.competition_id,
        source_url=body.source_url,
        dry_run=body.dry_run,
        min_coverage=body.min_coverage,
        manual_entries=_manual_entries(body.manual_entries),
    )
    if result.status == "failed":
        raise HTTPException(status_code=422, detail=result.error)
    return SeedNationalTeamEloResponse(
        season=result.season,
        competition_id=result.competition_id,
        matched=result.matched,
        total_teams=result.total_teams,
        coverage_pct=result.coverage_pct,
        unmatched=result.unmatched,
        source_date=result.source_date,
        dry_run=result.dry_run,
        status=result.status,
        error=result.error,
    )


def _manual_entries(
    entries: list[ManualNationalTeamEloSchema] | None,
) -> list[NationalTeamEloEntry] | None:
    if entries is None:
        return None
    return [
        NationalTeamEloEntry(
            country_name=entry.country_name,
            elo_raw=entry.elo_raw,
            rank=entry.rank,
            source_date=entry.source_date,
        )
        for entry in entries
    ]


@router.get(
    "/national-teams/coverage",
    response_model=NationalTeamEloCoverageResponse,
    dependencies=[Depends(require_admin_key)],
)
async def get_national_team_elo_coverage(
    use_case: Annotated[
        GetNationalTeamEloCoverageUseCase,
        Depends(get_national_team_elo_coverage_use_case),
    ],
    season: str = Query(...),
    competition_id: int | None = Query(default=None),
) -> NationalTeamEloCoverageResponse:
    """Audit World Cup team-strength coverage before recalculation."""
    result = await use_case.execute(season=season, competition_id=competition_id)
    if result.status == "failed":
        raise HTTPException(status_code=404, detail=result.error)
    return NationalTeamEloCoverageResponse(
        season=result.season,
        competition_id=result.competition_id,
        total_teams=result.total_teams,
        teams_with_strength=result.teams_with_strength,
        missing=result.missing,
        coverage_pct=result.coverage_pct,
        rows=[
            NationalTeamEloCoverageRowSchema(
                team_id=row.team_id,
                team_name=row.team_name,
                competition_id=row.competition_id,
                strength=row.strength,
                elo_raw=row.elo_raw,
                source=row.source,
            )
            for row in result.rows
        ],
        status=result.status,
        error=result.error,
    )
