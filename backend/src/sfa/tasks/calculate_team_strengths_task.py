import asyncio
import logging

from sfa.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def calculate_team_strengths_task(
    self,
    season: str,
    competition_id: int,
    matchday: int | None = None,
    league_factor: float = 1.0,
):
    """Calculate team strength ratings for a competition season."""
    try:
        asyncio.run(_run(season, competition_id, matchday, league_factor))
    except Exception as exc:
        logger.error(
            "[calculate_team_strengths_task] Failed season=%s competition_id=%d: %s",
            season, competition_id, exc,
        )
        raise self.retry(exc=exc)


async def _run(
    season: str,
    competition_id: int,
    matchday: int | None,
    league_factor: float,
) -> None:
    from sfa.application.use_cases.calculate_team_strengths import CalculateTeamStrengthsUseCase
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.repositories.team_strength_repository import TeamStrengthRepository

    async with AsyncSessionLocal() as session:
        repo = TeamStrengthRepository(session)
        use_case = CalculateTeamStrengthsUseCase(repo)
        result = await use_case.execute(
            season=season,
            competition_id=competition_id,
            matchday=matchday,
            league_factor=league_factor,
        )
        await session.commit()

    logger.info(
        "[calculate_team_strengths_task] Done season=%s competition_id=%d "
        "teams_processed=%d status=%s",
        season, competition_id, result.teams_processed, result.status,
    )
