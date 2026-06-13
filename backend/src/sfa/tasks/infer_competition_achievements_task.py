import asyncio
import logging

from sfa.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="sfa.tasks.infer_competition_achievements_task",
    max_retries=2,
    default_retry_delay=300,
)
def infer_competition_achievements_task(
    self,
    competition_id: int,
    season: str,
    rules_version_id: int,
):
    """Infer and upsert competition achievements from fixture data for one competition."""
    try:
        asyncio.run(_run(competition_id, season, rules_version_id))
    except Exception as exc:
        logger.error(
            "[infer_competition_achievements_task] Failed competition_id=%d season=%s: %s",
            competition_id, season, exc,
        )
        raise self.retry(exc=exc)


async def _run(competition_id: int, season: str, rules_version_id: int) -> None:
    from sfa.application.use_cases.infer_competition_achievements import (
        InferCompetitionAchievementsUseCase,
    )
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.repositories.competition_achievement_repository import (
        CompetitionAchievementRepository,
    )
    from sfa.infrastructure.repositories.infer_achievements_repository import (
        InferAchievementsRepository,
    )
    from sfa.infrastructure.repositories.scoring_rules_version_repository import (
        ScoringRulesVersionRepository,
    )

    async with AsyncSessionLocal() as session:
        use_case = InferCompetitionAchievementsUseCase(
            infer_repo=InferAchievementsRepository(session),
            achievement_repo=CompetitionAchievementRepository(session),
            rules_version_repo=ScoringRulesVersionRepository(session),
        )
        result = await use_case.execute(
            competition_id=competition_id,
            season=season,
            rules_version_id=rules_version_id,
        )
        await session.commit()

    logger.info(
        "[infer_competition_achievements_task] Done competition_id=%d season=%s "
        "skipped=%s upserted=%d phases=%s",
        competition_id, season, result.skipped,
        result.achievements_upserted, result.phases_found,
    )
