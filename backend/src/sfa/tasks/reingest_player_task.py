from __future__ import annotations

import asyncio
import logging

from sfa.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="sfa.reingest_player",
    max_retries=2,
    default_retry_delay=60,
    time_limit=600,
)
def reingest_player_task(
    self,
    player_id: int,
    season: int,
    competition_id: int | None = None,
) -> dict:
    """Re-ingest goal/assist events for a player and recalculate their scores."""
    try:
        return asyncio.run(_run(player_id, season, competition_id))
    except Exception as exc:
        logger.exception(
            "[reingest_player_task] Failed player_id=%d season=%d: %s",
            player_id, season, exc,
        )
        raise self.retry(exc=exc)


async def _run(
    player_id: int,
    season: int,
    competition_id: int | None,
) -> dict:
    from sfa.application.use_cases.calculate_scores_for_rules_version import (
        CalculateScoresForRulesVersionUseCase,
    )
    from sfa.application.use_cases.reingest_player import ReingestPlayerUseCase
    from sfa.core.config import get_settings
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.providers.api_football import APIFootballProvider
    from sfa.infrastructure.repositories.ingestion_repository import IngestionRepository
    from sfa.infrastructure.repositories.player_event_score_repository import (
        PlayerEventScoreRepository,
    )
    from sfa.infrastructure.repositories.scoring_rules_version_repository import (
        ScoringRulesVersionRepository,
    )

    settings = get_settings()
    provider = APIFootballProvider(
        settings.API_FOOTBALL_KEY,
        settings.API_FOOTBALL_BASE_URL,
    )

    async with AsyncSessionLocal() as session:
        ingestion_repo = IngestionRepository(session)
        rules_version_repo = ScoringRulesVersionRepository(session)
        event_score_repo = PlayerEventScoreRepository(session)
        scoring_uc = CalculateScoresForRulesVersionUseCase(
            rules_version_repo, event_score_repo
        )
        uc = ReingestPlayerUseCase(provider, ingestion_repo, rules_version_repo, scoring_uc)
        result = await uc.execute(player_id, season, competition_id)
        await session.commit()

    return {
        "player_id": result.player_id,
        "season": result.season,
        "fixtures_reingested": result.fixtures_reingested,
        "events_ingested": result.events_ingested,
        "scores_recalculated": result.scores_recalculated,
        "status": result.status,
        "error": result.error,
    }
