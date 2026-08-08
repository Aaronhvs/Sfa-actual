from __future__ import annotations

import asyncio
import logging

from sfa.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="sfa.tasks.generate_ranking_explanations_task",
    max_retries=0,
    time_limit=300,
)
def generate_ranking_explanations_task(
    self,
    season: str,
    rules_version_id: int | None,
    competition_id: int | None,
    scope: str,
    limit: int = 10,
    force: bool = False,
    use_total: bool = True,
    scope_key: str | None = None,
) -> None:
    asyncio.run(
        _run(
            season,
            rules_version_id,
            competition_id,
            scope,
            limit,
            force,
            use_total,
            scope_key,
        )
    )


async def _run(
    season: str,
    rules_version_id: int | None,
    competition_id: int | None,
    scope: str,
    limit: int,
    force: bool,
    use_total: bool,
    scope_key: str | None = None,
) -> None:
    from sfa.application.use_cases.generate_ranking_explanations import (
        GenerateRankingExplanationsUseCase,
    )
    from sfa.core.config import get_settings
    from sfa.domain.ranking_explanation_ports import RankingExplanationRequestDTO
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.providers.ranking_explanation_writer import (
        DeterministicRankingExplanationWriter,
        OpenAICompatibleRankingExplanationWriter,
    )
    from sfa.infrastructure.repositories.ranking_explanation_repository import (
        RankingExplanationRepository,
    )
    from sfa.infrastructure.repositories.season_repository import SeasonRepository
    from sfa.infrastructure.repositories.sfa_score_repository import SFAScoreRepository

    logger.info(
        "[generate_ranking_explanations_task] START season=%s competition_id=%s rules_version_id=%s scope=%s",
        season,
        competition_id,
        rules_version_id,
        scope,
    )
    settings = get_settings()
    writer = DeterministicRankingExplanationWriter()
    if (
        settings.AI_EXPLANATIONS_ENABLED
        and settings.AI_EXPLANATIONS_PROVIDER.lower() in {"openai", "openai-compatible"}
        and settings.AI_EXPLANATIONS_API_KEY
    ):
        writer = OpenAICompatibleRankingExplanationWriter(
            api_key=settings.AI_EXPLANATIONS_API_KEY,
            base_url=settings.AI_EXPLANATIONS_BASE_URL,
            model=settings.AI_EXPLANATIONS_MODEL,
            timeout_seconds=settings.AI_EXPLANATIONS_TIMEOUT_SECONDS,
            max_output_tokens=settings.AI_EXPLANATIONS_MAX_OUTPUT_TOKENS_PER_PLAYER,
        )

    async with AsyncSessionLocal() as session:
        use_case = GenerateRankingExplanationsUseCase(
            score_repo=SFAScoreRepository(session),
            explanation_repo=RankingExplanationRepository(session),
            writer=writer,
            season_repo=SeasonRepository(session),
        )
        result = await use_case.execute(
            RankingExplanationRequestDTO(
                season=season,
                competition_id=competition_id,
                rules_version_id=rules_version_id,
                scope=scope,
                limit=min(max(limit, 1), 10),
                use_total=use_total,
                force=force,
                scope_key=scope_key,
            )
        )
        await session.commit()

    logger.info(
        "[generate_ranking_explanations_task] DONE season=%s scope=%s generated=%s "
        "fallback=%s skipped=%s failed=%s cost=%s",
        result.season,
        result.scope,
        result.generated,
        result.fallback,
        result.skipped,
        result.failed,
        result.estimated_cost_usd,
    )
