import asyncio
import logging

from sfa.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="sfa.tasks.recalculate_award_period_task",
    max_retries=0,
    time_limit=7200,
)
def recalculate_award_period_task(
    self,
    scope_key: str,
    rules_version_id: int,
    force_recalculate: bool = True,
    infer_achievements: bool = True,
):
    asyncio.run(
        _run(
            scope_key,
            rules_version_id,
            force_recalculate,
            infer_achievements,
        )
    )


async def _run(
    scope_key: str,
    rules_version_id: int,
    force_recalculate: bool,
    infer_achievements: bool,
) -> None:
    from sqlalchemy import text

    from sfa.core.config import get_settings
    from sfa.domain.season_scope import ScopeKind
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.repositories.scoring_rules_version_repository import (
        ScoringRulesVersionRepository,
    )
    from sfa.infrastructure.repositories.season_repository import SeasonRepository
    from sfa.infrastructure.repositories.team_strength_repository import (
        TeamStrengthRepository,
    )
    from sfa.tasks.elo_tasks import _run_elo_update
    from sfa.tasks.run_full_recalculation_task import _run as _run_full_recalculation

    lock_key = 41_000_000 + (sum(ord(char) for char in scope_key) % 10_000_000)
    async with AsyncSessionLocal() as lock_session:
        await lock_session.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_key})
        try:
            rules_version = await ScoringRulesVersionRepository(lock_session).get_version_by_id(
                rules_version_id
            )
            if rules_version is None:
                raise ValueError(f"Rules version {rules_version_id} not found")
            scope = await SeasonRepository(lock_session).resolve_scope(scope_key)
            if scope is None or scope.kind != ScopeKind.AWARD_PERIOD:
                raise ValueError(f"Scope {scope_key} is not an award period")

            logger.info(
                "[recalculate_award_period_task] START scope=%s rules_version_id=%d",
                scope_key,
                rules_version_id,
            )
            settings = get_settings()
            for source in scope.sources:
                strength_repo = TeamStrengthRepository(lock_session)
                club_pool = set(
                    await strength_repo.get_competition_ids_for_participant_kind(
                        source.season, "club"
                    )
                )
                source_club_ids = sorted(club_pool.intersection(source.competition_ids))
                if source_club_ids:
                    await _run_elo_update(
                        season=source.season,
                        competition_ids=source_club_ids,
                        default_k=30.0,
                        source="club_elo_v2",
                        use_seed_baseline=True,
                        require_seed_baseline=True,
                        initialize_missing_seed_baseline=False,
                    )
                national_pool = set(
                    await strength_repo.get_competition_ids_for_participant_kind(
                        source.season, "national_team"
                    )
                )
                source_national_ids = sorted(
                    national_pool.intersection(source.competition_ids)
                )
                if source_national_ids:
                    await _run_elo_update(
                        season=source.season,
                        competition_ids=source_national_ids,
                        default_k=settings.NATIONAL_TEAM_ELO_DEFAULT_K,
                        source="national_elo_v1",
                        use_seed_baseline=True,
                        require_seed_baseline=True,
                        initialize_missing_seed_baseline=False,
                    )

            recalculated_seasons: set[str] = set()
            for source in scope.sources:
                if source.season in recalculated_seasons:
                    continue
                await _run_full_recalculation(
                    rules_version_id=rules_version_id,
                    season=source.season,
                    force_recalculate=force_recalculate,
                    infer_achievements=infer_achievements,
                    queue_explanations=False,
                )
                recalculated_seasons.add(source.season)

            from sfa.application.use_cases.infer_individual_honors import (
                InferIndividualHonorsUseCase,
            )
            from sfa.infrastructure.repositories.individual_honor_repository import (
                IndividualHonorRepository,
            )

            honor_use_case = InferIndividualHonorsUseCase(
                IndividualHonorRepository(lock_session),
                SeasonRepository(lock_session),
                ScoringRulesVersionRepository(lock_session),
            )
            await honor_use_case.execute(scope.key, rules_version_id)
            available_scopes = await SeasonRepository(lock_session).get_available_seasons()
            source_seasons = {source.season for source in scope.sources}
            for item in available_scopes:
                if item.kind == "tournament" and item.season in source_seasons and item.key:
                    await honor_use_case.execute(item.key, rules_version_id)
            await lock_session.commit()
        finally:
            await lock_session.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key}
            )
            await lock_session.commit()
    from sfa.tasks.generate_ranking_explanations_task import (
        generate_ranking_explanations_task,
    )

    explanation_task = generate_ranking_explanations_task.delay(
        scope.sources[0].season,
        rules_version_id,
        None,
        "award_period",
        3,
        False,
        True,
        scope.key,
    )
    logger.info(
        "[recalculate_award_period_task] DONE scope=%s rules_version_id=%d "
        "explanations_task_id=%s",
        scope_key,
        rules_version_id,
        explanation_task.id,
    )
