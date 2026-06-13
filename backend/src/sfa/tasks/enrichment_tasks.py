import asyncio
import logging

from sfa.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def backfill_fixture_stats_task(self, competition_id: int, season: str):
    """Re-fetch player stats from API-Football for all fixtures in a competition/season."""
    try:
        result = asyncio.run(_run_backfill_fixture_stats(competition_id, season))
        return result
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=1)
def enrich_all_task(self, season: str, season_int: int):
    """Recalculate SFA scores for all leagues (API-Football is now the sole stats source)."""
    try:
        asyncio.run(_run_recalculate_all(season))
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def recalculate_task(self, competition_id: int, season: str):
    """Recalculate SFA scores for a league (useful after parameter changes)."""
    try:
        asyncio.run(_run_recalculate(competition_id, season))
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(name="enrich_player_positions_task", bind=True, max_retries=0)
def enrich_player_positions_task(self, batch_size: int = 500) -> dict:
    """Enrich player positions from Transfermarkt. Rate-limited to 1 request per second."""
    return asyncio.run(_run_enrich_player_positions(batch_size))


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------


async def _run_backfill_fixture_stats(competition_id: int, season: str) -> dict:
    from sfa.application.use_cases.backfill_fixture_stats import BackfillFixtureStatsUseCase
    from sfa.core.config import get_settings
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.providers.api_football import APIFootballProvider
    from sfa.infrastructure.repositories.ingestion_repository import IngestionRepository

    settings = get_settings()
    provider = APIFootballProvider(settings.API_FOOTBALL_KEY, settings.API_FOOTBALL_BASE_URL)

    async with AsyncSessionLocal() as session:
        repo = IngestionRepository(session)
        use_case = BackfillFixtureStatsUseCase(repo, provider)
        result = await use_case.execute(competition_id, season)
        await session.commit()
    return result


async def _run_recalculate(competition_id: int, season: str) -> None:
    from sfa.application.use_cases.recalculate_scores import RecalculateScoresUseCase
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.repositories.enrichment_repository import EnrichmentRepository

    async with AsyncSessionLocal() as session:
        repo = EnrichmentRepository(session)
        use_case = RecalculateScoresUseCase(repo)
        result = await use_case.execute(competition_id, season)
        await session.commit()
    return result


async def _run_recalculate_all(season: str) -> None:
    from sfa.application.use_cases.ingest_competition import LEAGUES

    for league in LEAGUES:
        await _run_recalculate(league.id, season)


async def _run_enrich_player_positions(batch_size: int) -> dict:
    from sfa.application.use_cases.enrich_player_positions import EnrichPlayerPositionsUseCase
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.providers.transfermarkt_scraper import TransfermarktScraper
    from sfa.infrastructure.repositories.enrich_position_repository import EnrichPositionRepository
    from sfa.infrastructure.repositories.player_tm_id_repository import PlayerTmIdRepository

    async with AsyncSessionLocal() as session:
        use_case = EnrichPlayerPositionsUseCase(
            provider=TransfermarktScraper(),
            tm_id_repo=PlayerTmIdRepository(session),
            enrich_repo=EnrichPositionRepository(session),
        )
        result = await use_case.execute(batch_size=batch_size)
        await session.commit()
        return {
            "total_processed": result.total_processed,
            "matched": result.matched,
            "position_updated": result.position_updated,
            "unmatched": result.unmatched,
            "failed": result.failed,
            "skipped_already_tm": result.skipped_already_tm,
        }
