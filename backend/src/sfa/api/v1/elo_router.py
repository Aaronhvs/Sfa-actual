from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.api.v1.schemas.elo_schemas import (
    ClubEloSeedResolutionSchema,
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
from sfa.domain.scoring_ports import ManualClubEloEntry, NationalTeamEloEntry
from sfa.infrastructure.database import get_db

router = APIRouter(prefix="/admin/elo", tags=["elo"])


@router.post(
    "/seed",
    response_model=SeedClubEloResponse,
    dependencies=[Depends(require_admin_key)],
)
async def seed_clubelo(
    body: SeedClubEloRequest,
    use_case: Annotated[SeedClubEloUseCase, Depends(get_seed_clubelo_use_case)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SeedClubEloResponse:
    """Download ClubElo snapshot and populate team_strengths."""
    result = await use_case.execute(
        date_str=body.date_str,
        season=body.season,
        manual_entries=[
            ManualClubEloEntry(
                team_name=entry.team_name,
                elo_raw=entry.elo_raw,
                reason=entry.reason,
                source_reference=entry.source_reference,
                source_date=entry.source_date,
                approved_by=entry.approved_by,
            )
            for entry in body.manual_entries or []
        ],
        dry_run=body.dry_run,
    )
    if result.status == "failed":
        await db.rollback()
        status_code = 503 if result.provider_error else 422
        raise HTTPException(
            status_code=status_code,
            detail={
                "error": result.error,
                "matched": result.matched,
                "unmatched": result.unmatched,
                "coverage_pct": result.coverage_pct,
                "source_counts": result.source_counts,
                "history_requests": result.history_requests,
                "blockers": result.blockers,
                "resolutions": [resolution.__dict__ for resolution in result.resolutions],
            },
        )
    if not body.dry_run:
        await db.commit()
    return SeedClubEloResponse(
        date_str=result.date_str,
        season=result.season,
        matched=result.matched,
        cutoff=result.cutoff,
        total_teams=result.total_teams,
        unmatched=result.unmatched,
        coverage_pct=result.coverage_pct,
        source_counts=result.source_counts,
        history_requests=result.history_requests,
        blockers=result.blockers,
        resolutions=[
            ClubEloSeedResolutionSchema(
                team_name=row.team_name,
                status=row.status,
                elo_raw=row.elo_raw,
                source=row.source,
                blocker=row.blocker,
            )
            for row in result.resolutions
        ],
        dry_run=result.dry_run,
        status=result.status,
        error=result.error,
    )


@router.post(
    "/recalculate",
    response_model=RecalculateEloResponse,
    dependencies=[Depends(require_admin_key)],
)
async def recalculate_elo(
    body: RecalculateEloRequest,
    use_case: Annotated[CalculateEloRatingsUseCase, Depends(get_calculate_elo_use_case)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RecalculateEloResponse:
    """Recalculate ELO ratings by processing fixtures in chronological order."""
    result = await use_case.execute(
        season=body.season,
        competition_ids=body.competition_ids,
        k_factors=body.k_factors,
        default_k=body.default_k,
        source=("club_elo_v2" if body.participant_kind == "club" else "national_elo_v1"),
        use_seed_baseline=True,
        require_seed_baseline=True,
        initialize_missing_seed_baseline=False,
    )
    if result.status == "failed":
        await db.rollback()
        raise HTTPException(status_code=500, detail=result.error)
    await db.commit()
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
    db: Annotated[AsyncSession, Depends(get_db)],
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
        await db.rollback()
        raise HTTPException(status_code=422, detail=result.error)
    if not body.dry_run:
        await db.commit()
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
