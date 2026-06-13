import asyncio
import logging

from sfa.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def calculate_scores_for_rules_version_task(
    self,
    rules_version_id: int,
    season: str,
    competition_id: int | None = None,
    match_id: int | None = None,
    player_id: int | None = None,
    force_recalculate: bool = False,
):
    """Recalculate player event scores and season scores for a specific rules version."""
    try:
        asyncio.run(
            _run_calculate_scores_for_rules_version(
                rules_version_id=rules_version_id,
                season=season,
                competition_id=competition_id,
                match_id=match_id,
                player_id=player_id,
                force_recalculate=force_recalculate,
            )
        )
    except Exception as exc:
        logger.error(
            "[calculate_scores_for_rules_version_task] Failed rules_version_id=%d season=%s: %s",
            rules_version_id, season, exc,
        )
        raise self.retry(exc=exc)


async def _run_calculate_scores_for_rules_version(
    rules_version_id: int,
    season: str,
    competition_id: int | None,
    match_id: int | None,
    player_id: int | None,
    force_recalculate: bool,
) -> None:
    from sfa.application.use_cases.calculate_scores_for_rules_version import (
        CalculateScoresForRulesVersionUseCase,
    )
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.repositories.player_event_score_repository import (
        PlayerEventScoreRepository,
    )
    from sfa.infrastructure.repositories.scoring_rules_version_repository import (
        ScoringRulesVersionRepository,
    )

    async with AsyncSessionLocal() as session:
        rules_version_repo = ScoringRulesVersionRepository(session)
        event_score_repo = PlayerEventScoreRepository(session)

        use_case = CalculateScoresForRulesVersionUseCase(
            rules_version_repo=rules_version_repo,
            event_score_repo=event_score_repo,
        )
        result = await use_case.execute(
            rules_version_id=rules_version_id,
            season=season,
            competition_id=competition_id,
            match_id=match_id,
            player_id=player_id,
            force_recalculate=force_recalculate,
        )
        await session.commit()

    logger.info(
        "[calculate_scores_for_rules_version_task] Done rules_version_id=%d season=%s "
        "events_calculated=%d players_updated=%d status=%s",
        rules_version_id, season,
        result.events_calculated, result.players_updated, result.status,
    )
