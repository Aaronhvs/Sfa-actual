import asyncio
import logging

from sfa.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="sfa.tasks.run_full_recalculation_task",
    max_retries=0,
    time_limit=3600,
)
def run_full_recalculation_task(
    self,
    rules_version_id: int,
    season: str,
    force_recalculate: bool = True,
    infer_achievements: bool = True,
    explanation_competition_id: int | None = None,
    explanation_scope: str = "ranking",
):
    """Run scoring recalculation, achievement inference, and achievement bonuses in one task."""
    asyncio.run(
        _run(
            rules_version_id,
            season,
            force_recalculate,
            infer_achievements,
            explanation_competition_id=explanation_competition_id,
            explanation_scope=explanation_scope,
        )
    )


async def _run(
    rules_version_id: int,
    season: str,
    force_recalculate: bool,
    infer_achievements: bool = True,
    queue_explanations: bool = True,
    explanation_competition_id: int | None = None,
    explanation_scope: str = "ranking",
) -> None:
    from sfa.application.use_cases.run_full_recalculation import (
        RunFullRecalculationUseCase,
    )
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.repositories.competition_achievement_repository import (
        CompetitionAchievementRepository,
    )
    from sfa.infrastructure.repositories.infer_achievements_repository import (
        InferAchievementsRepository,
    )
    from sfa.infrastructure.repositories.player_event_score_repository import (
        PlayerEventScoreRepository,
    )
    from sfa.infrastructure.repositories.scoring_rules_version_repository import (
        ScoringRulesVersionRepository,
    )

    logger.info(
        "[run_full_recalculation_task] START rules_version_id=%d season=%s force=%s infer=%s",
        rules_version_id,
        season,
        force_recalculate,
        infer_achievements,
    )

    async with AsyncSessionLocal() as session:
        use_case = RunFullRecalculationUseCase(
            rules_version_repo=ScoringRulesVersionRepository(session),
            event_score_repo=PlayerEventScoreRepository(session),
            achievement_repo=CompetitionAchievementRepository(session),
            infer_repo=InferAchievementsRepository(session),
        )
        result = await use_case.execute(
            rules_version_id=rules_version_id,
            season=season,
            force_recalculate=force_recalculate,
            infer_achievements=infer_achievements,
        )
        if result.status == "completed":
            await session.commit()
        else:
            await session.rollback()

    logger.info(
        "[run_full_recalculation_task] DONE status=%s events=%s players=%s bonuses=%s",
        result.status,
        result.events_calculated,
        result.players_updated,
        result.achievement_bonuses_created,
    )
    if result.status != "completed":
        raise RuntimeError(result.error or "Full recalculation failed")
    if result.status == "completed" and queue_explanations:
        _queue_ranking_explanations_after_recalculation(
            season,
            rules_version_id,
            explanation_competition_id,
            explanation_scope,
        )


def _queue_ranking_explanations_after_recalculation(
    season: str,
    rules_version_id: int,
    competition_id: int | None = None,
    scope: str = "ranking",
) -> str:
    from sfa.core.config import get_settings
    from sfa.tasks.generate_ranking_explanations_task import (
        generate_ranking_explanations_task,
    )

    settings = get_settings()
    task = generate_ranking_explanations_task.delay(
        season,
        rules_version_id,
        competition_id,
        scope,
        settings.AI_EXPLANATIONS_TOP_N,
        False,
        True,
    )
    logger.info(
        "[run_full_recalculation_task] queued ranking explanations task_id=%s scope=%s force=%s top_n=%s",
        task.id,
        scope,
        False,
        settings.AI_EXPLANATIONS_TOP_N,
    )
    return str(task.id)
