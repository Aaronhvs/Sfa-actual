from __future__ import annotations

import asyncio
import logging

from sfa.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="sfa.ingest_fixture_events",
    max_retries=2,
    default_retry_delay=30,
    time_limit=120,
)
def ingest_fixture_events_task(self, fixture_external_id: int) -> dict:
    """Fetch and persist timeline events (goals, cards, subs) for a single fixture."""
    try:
        return asyncio.run(_run(fixture_external_id))
    except Exception as exc:
        logger.exception(
            "[ingest_fixture_events_task] Failed fixture_external_id=%d: %s",
            fixture_external_id, exc,
        )
        raise self.retry(exc=exc)


async def _run(fixture_external_id: int) -> dict:
    from sfa.core.config import get_settings
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.providers.api_football import APIFootballProvider
    from sfa.infrastructure.repositories.ingestion_repository import IngestionRepository

    settings = get_settings()
    provider = APIFootballProvider(
        settings.API_FOOTBALL_KEY,
        settings.API_FOOTBALL_BASE_URL,
    )

    async with AsyncSessionLocal() as session:
        repo = IngestionRepository(session)
        events = await provider.fetch_fixture_events(fixture_external_id)
        await repo.save_fixture_events(fixture_external_id, events)
        await session.commit()

    logger.info(
        "[ingest_fixture_events_task] Saved %d raw events for fixture_external_id=%d",
        len(events), fixture_external_id,
    )
    return {"fixture_external_id": fixture_external_id, "raw_events_fetched": len(events)}
