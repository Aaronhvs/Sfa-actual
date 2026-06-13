import asyncio
import logging

from sfa.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="sfa.tasks.infer_all_competition_achievements_task",
    max_retries=0,
    time_limit=3600,
)
def infer_all_competition_achievements_task(
    self,
    season: str,
    rules_version_id: int,
):
    """Infer and upsert competition achievements for ALL knockout competitions in a season."""
    asyncio.run(_run(season, rules_version_id))


async def _run(season: str, rules_version_id: int) -> None:
    from sfa.application.use_cases.infer_competition_achievements import (
        InferAllCompetitionAchievementsUseCase,
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
        use_case = InferAllCompetitionAchievementsUseCase(
            infer_repo=InferAchievementsRepository(session),
            achievement_repo=CompetitionAchievementRepository(session),
            rules_version_repo=ScoringRulesVersionRepository(session),
        )
        result = await use_case.execute(season=season, rules_version_id=rules_version_id)
        await session.commit()

    logger.info(
        "[infer_all_competition_achievements_task] Done season=%s "
        "processed=%d skipped=%d total_upserted=%d",
        season, result.competitions_processed,
        result.competitions_skipped, result.total_achievements_upserted,
    )
