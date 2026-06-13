import asyncio
import logging

from sfa.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def calculate_achievement_bonuses_task(
    self,
    season: str,
    competition_id: int,
    rules_version_id: int,
):
    """Calculate player achievement bonuses for a competition season."""
    try:
        asyncio.run(_run(season, competition_id, rules_version_id))
    except Exception as exc:
        logger.error(
            "[calculate_achievement_bonuses_task] Failed season=%s competition_id=%d: %s",
            season, competition_id, exc,
        )
        raise self.retry(exc=exc)


async def _run(season: str, competition_id: int, rules_version_id: int) -> None:
    from sfa.application.use_cases.calculate_achievement_bonuses import (
        CalculateAchievementBonusesUseCase,
    )
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.repositories.competition_achievement_repository import (
        CompetitionAchievementRepository,
    )
    from sfa.infrastructure.repositories.scoring_rules_version_repository import (
        ScoringRulesVersionRepository,
    )

    async with AsyncSessionLocal() as session:
        achievement_repo = CompetitionAchievementRepository(session)
        rules_version_repo = ScoringRulesVersionRepository(session)
        use_case = CalculateAchievementBonusesUseCase(achievement_repo, rules_version_repo)
        result = await use_case.execute(
            season=season,
            competition_id=competition_id,
            rules_version_id=rules_version_id,
        )
        await session.commit()

    logger.info(
        "[calculate_achievement_bonuses_task] Done season=%s competition_id=%d "
        "bonuses_created=%d players_updated=%d status=%s",
        season, competition_id, result.bonuses_created, result.players_updated, result.status,
    )
