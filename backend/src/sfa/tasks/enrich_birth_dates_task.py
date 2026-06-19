import asyncio
import logging

from sfa.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="sfa.enrich_player_birth_dates",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def enrich_player_birth_dates_task(
    self,
    season: str,
    force_update: bool = False,
) -> dict:
    """Enrich players.birth_date from API-Football squad endpoint plus individual fallback."""
    try:
        return asyncio.run(_run(season, force_update))
    except Exception as exc:
        logger.error("[enrich_player_birth_dates_task] Failed: %s", exc)
        raise self.retry(exc=exc)


async def _run(season: str, force_update: bool) -> dict:
    from sfa.application.use_cases.enrich_player_birth_dates import EnrichPlayerBirthDatesUseCase
    from sfa.core.config import get_settings
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.providers.api_football import APIFootballProvider
    from sfa.infrastructure.repositories.birth_date_enrichment_repository import (
        BirthDateEnrichmentRepository,
    )

    settings = get_settings()
    provider = APIFootballProvider(settings.API_FOOTBALL_KEY, settings.API_FOOTBALL_BASE_URL)

    async with AsyncSessionLocal() as session:
        repo = BirthDateEnrichmentRepository(session)
        use_case = EnrichPlayerBirthDatesUseCase(provider=provider, repo=repo)
        result = await use_case.execute(season=season, force_update=force_update)
        await session.commit()

    return {
        "teams_processed": result.teams_processed,
        "players_updated": result.players_updated,
        "players_skipped": result.players_skipped,
        "status": result.status,
    }
