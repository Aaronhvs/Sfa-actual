import asyncio
import logging

from sfa.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="sfa.tasks.infer_individual_honors_task",
    max_retries=1,
    default_retry_delay=60,
)
def infer_individual_honors_task(
    self,
    scope_key: str,
    rules_version_id: int,
) -> None:
    try:
        asyncio.run(_run(scope_key, rules_version_id))
    except Exception as exc:
        logger.error(
            "[infer_individual_honors_task] Failed scope=%s: %s",
            scope_key, exc,
        )
        raise self.retry(exc=exc)


async def _run(scope_key: str, rules_version_id: int) -> None:
    from sfa.application.use_cases.infer_individual_honors import (
        InferIndividualHonorsUseCase,
    )
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.repositories.individual_honor_repository import (
        IndividualHonorRepository,
    )
    from sfa.infrastructure.repositories.scoring_rules_version_repository import (
        ScoringRulesVersionRepository,
    )
    from sfa.infrastructure.repositories.season_repository import SeasonRepository

    async with AsyncSessionLocal() as session:
        result = await InferIndividualHonorsUseCase(
            IndividualHonorRepository(session),
            SeasonRepository(session),
            ScoringRulesVersionRepository(session),
        ).execute(scope_key, rules_version_id)
        await session.commit()
    logger.info(
        "[infer_individual_honors_task] Done scope=%s honors=%d players=%d",
        result.scope_key, result.honors_created, result.players_awarded,
    )
