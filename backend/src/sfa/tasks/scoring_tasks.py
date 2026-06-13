import asyncio

from sfa.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def calculate_competition_scores_task(self, competition_id: int, season: int):
    """DEPRECATED: use run_full_recalculation_task instead. Legacy pipeline without rules_version_id."""
    try:
        asyncio.run(_run_calculate_competition_scores(competition_id, season))
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=1)
def calculate_all_scores_task(self, season: int):
    """DEPRECATED: use run_full_recalculation_task instead. Legacy pipeline without rules_version_id."""
    try:
        asyncio.run(_run_calculate_all_scores(season))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _run_calculate_competition_scores(competition_id: int, season: int):
    from sfa.application.use_cases.calculate_competition_scores import CalculateCompetitionScoresUseCase
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.repositories.scoring_repository import ScoringRepository

    async with AsyncSessionLocal() as session:
        repo = ScoringRepository(session)
        use_case = CalculateCompetitionScoresUseCase(repo)
        result = await use_case.execute(competition_id, str(season))
        await session.commit()

    return result


async def _run_calculate_all_scores(season: int):
    from sfa.application.use_cases.calculate_all_scores import CalculateAllScoresUseCase
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.repositories.scoring_repository import ScoringRepository

    async with AsyncSessionLocal() as session:
        repo = ScoringRepository(session)
        use_case = CalculateAllScoresUseCase(repo)
        results = await use_case.execute(str(season))
        await session.commit()

    return results
