from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.api.v1.schemas.ingestion_status import (
    CompetitionIngestionStatusResponseSchema,
)
from sfa.application.use_cases.fix_player_positions import (
    FixPlayerPositionsResult,
    FixPlayerPositionsUseCase,
)
from sfa.application.use_cases.get_ingestion_status import GetIngestionStatusUseCase
from sfa.application.use_cases.enrich_player_birth_dates import EnrichPlayerBirthDatesUseCase
from sfa.core.dependencies import (
    get_db,
    get_enrich_player_birth_dates_use_case,
    get_fix_player_positions_use_case,
    get_ingestion_status_use_case,
    get_reingest_player_use_case,
    require_admin_key,
)
from sfa.tasks.enrichment_tasks import (
    backfill_fixture_stats_task,
    enrich_all_task,
    enrich_player_positions_task,
    recalculate_task,
)
from sfa.tasks.ingestion_tasks import ingest_all_competitions_task, ingest_competition_task

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_key)])

CURRENT_SEASON = 2024
CURRENT_SEASON_STR = "2024"


@router.post("/ingest/{league_id}")
async def trigger_ingest_competition(
    league_id: int,
    season: int = Query(default=CURRENT_SEASON),
    force: bool = Query(default=False),
):
    """Trigger ingestion of a specific league as an async Celery task."""
    task = ingest_competition_task.delay(league_id, season, force)
    return {
        "task_id": task.id,
        "league_id": league_id,
        "season": season,
        "force": force,
    }


@router.post("/ingest-all")
async def trigger_ingest_all(
    season: int = Query(default=CURRENT_SEASON),
    force: bool = Query(default=False),
):
    """Trigger ingestion of all configured leagues as an async Celery task."""
    task = ingest_all_competitions_task.delay(season, force)
    return {"task_id": task.id, "season": season, "force": force}


@router.get(
    "/ingestion-logs",
    response_model=list[CompetitionIngestionStatusResponseSchema],
)
async def get_ingestion_logs(
    use_case: Annotated[
        GetIngestionStatusUseCase, Depends(get_ingestion_status_use_case)
    ],
    season: int = Query(default=CURRENT_SEASON),
):
    """Return consolidated ingestion status for compatibility."""
    return await use_case.execute(str(season))


@router.get(
    "/ingestion-status",
    response_model=list[CompetitionIngestionStatusResponseSchema],
)
async def get_ingestion_status(
    use_case: Annotated[
        GetIngestionStatusUseCase, Depends(get_ingestion_status_use_case)
    ],
    season: int = Query(default=CURRENT_SEASON),
):
    """Return ingestion status for every configured competition."""
    return await use_case.execute(str(season))


@router.post("/backfill-fixture-stats")
async def trigger_backfill_fixture_stats(
    competition_id: int = Query(...),
    season: str = Query(default=CURRENT_SEASON_STR),
):
    """Re-fetch player stats from API-Football for all existing fixtures in a competition/season."""
    task = backfill_fixture_stats_task.delay(competition_id, season)
    return {"task_id": task.id, "competition_id": competition_id, "season": season}


@router.post("/enrich-all")
async def trigger_enrich_all(
    season: str = Query(default=CURRENT_SEASON_STR),
    season_int: int = Query(default=CURRENT_SEASON),
):
    """Recalculate SFA scores for all leagues."""
    task = enrich_all_task.delay(season, season_int)
    return {"task_id": task.id, "season": season}


@router.post("/recalculate/{competition_id}")
async def trigger_recalculate(
    competition_id: int,
    season: str = Query(default=CURRENT_SEASON_STR),
):
    """Recalculate SFA scores for a league (useful after parameter changes)."""
    task = recalculate_task.delay(competition_id, season)
    return {"task_id": task.id, "competition_id": competition_id}


async def _run_fix_player_positions(
    use_case: FixPlayerPositionsUseCase,
    db: AsyncSession,
) -> FixPlayerPositionsResult:
    result = await use_case.execute()
    await db.commit()
    return result


@router.post("/players/fix-positions")
async def fix_player_positions(
    use_case: Annotated[
        FixPlayerPositionsUseCase, Depends(get_fix_player_positions_use_case)
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FixPlayerPositionsResult:
    """Fix existing player positions using stored player_stats heuristics."""
    return await _run_fix_player_positions(use_case, db)


@router.post("/fix-player-positions")
async def fix_player_positions_legacy(
    use_case: Annotated[
        FixPlayerPositionsUseCase, Depends(get_fix_player_positions_use_case)
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FixPlayerPositionsResult:
    """Compatibility endpoint for the spec wording."""
    return await _run_fix_player_positions(use_case, db)


@router.post("/players/enrich-positions", status_code=status.HTTP_202_ACCEPTED)
async def trigger_enrich_player_positions(
    body: dict | None = Body(default=None),
    batch_size: int = Query(default=500, ge=1, le=5000),
):
    """Enrich player positions from Transfermarkt in a Celery background task."""
    payload = body or {}
    dry_run = bool(payload.get("dry_run", False))
    season = payload.get("season", CURRENT_SEASON_STR)
    requested_batch_size = int(payload.get("batch_size", batch_size))
    requested_batch_size = max(1, min(5000, requested_batch_size))

    if dry_run:
        return {
            "status": "accepted",
            "dry_run": True,
            "season": season,
            "batch_size": requested_batch_size,
            "task_id": None,
        }

    task = enrich_player_positions_task.delay(requested_batch_size, season)
    return {
        "status": "queued",
        "dry_run": False,
        "season": season,
        "batch_size": requested_batch_size,
        "task_id": task.id,
    }


@router.post("/players/{player_id}/reingest", status_code=status.HTTP_202_ACCEPTED)
async def trigger_player_reingest(
    player_id: int,
    _use_case: Annotated[object, Depends(get_reingest_player_use_case)],
    season: int = Query(default=CURRENT_SEASON),
    competition_id: int | None = Query(default=None),
) -> dict:
    """Re-ingest goal/assist events for a specific player and recalculate their scores.

    Fetches only the fixtures this player already participated in (from player_stats),
    deletes their existing events, re-ingests from API-Football, and recalculates scores.
    Costs ~2 API requests per fixture (events + players endpoints).
    """
    from sfa.tasks.reingest_player_task import reingest_player_task

    task = reingest_player_task.delay(player_id, season, competition_id)
    return {
        "task_id": task.id,
        "player_id": player_id,
        "season": season,
        "competition_id": competition_id,
        "status": "queued",
    }


@router.post(
    "/enrich-birth-dates",
    status_code=status.HTTP_200_OK,
)
async def trigger_enrich_birth_dates(
    use_case: Annotated[EnrichPlayerBirthDatesUseCase, Depends(get_enrich_player_birth_dates_use_case)],
    db: Annotated[AsyncSession, Depends(get_db)],
    season: str = Query(default=CURRENT_SEASON_STR),
    force_update: bool = Query(default=False),
) -> dict:
    """Enrich players.birth_date from API-Football squad endpoint plus individual fallback.

    Only processes teams where at least one player is missing birth_date (unless force_update=True).
    """
    result = await use_case.execute(season=season, force_update=force_update)
    await db.commit()
    return {
        "teams_processed": result.teams_processed,
        "players_updated": result.players_updated,
        "players_skipped": result.players_skipped,
        "status": result.status,
    }


@router.post(
    "/fixtures/{fixture_external_id}/ingest-events",
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_fixture_events_ingest(
    fixture_external_id: int,
    _key: Annotated[None, Depends(require_admin_key)],
) -> dict:
    """Fetch and persist timeline events (goals, cards, subs) for a single fixture.

    Use this to backfill events for already-ingested fixtures.
    Costs 1 API-Football request.
    """
    from sfa.tasks.ingest_fixture_events_task import ingest_fixture_events_task

    task = ingest_fixture_events_task.delay(fixture_external_id)
    return {
        "task_id": task.id,
        "fixture_external_id": fixture_external_id,
        "status": "queued",
    }
