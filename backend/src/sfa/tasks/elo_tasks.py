import asyncio
import logging

from sfa.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def seed_clubelo_task(self, date_str: str, season: str):
    """One-time seed: download ClubElo and populate team_strengths."""
    try:
        asyncio.run(_run_seed(date_str, season))
    except Exception as exc:
        logger.error("[seed_clubelo_task] Failed date=%s season=%s: %s", date_str, season, exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def seed_national_team_elo_task(
    self,
    season: str,
    competition_id: int | None = None,
    source_url: str | None = None,
    min_coverage: float = 100.0,
):
    """Seed national-team ELO ratings into team_strengths."""
    try:
        asyncio.run(_run_national_team_seed(season, competition_id, source_url, min_coverage))
    except Exception as exc:
        logger.error("[seed_national_team_elo_task] Failed season=%s: %s", season, exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def apply_elo_update_task(self, season: str, competition_ids: list[int]):
    """Recalculate ELO ratings after ingestion."""
    try:
        asyncio.run(_run_elo_update(season, competition_ids))
    except Exception as exc:
        logger.error(
            "[apply_elo_update_task] Failed season=%s competition_ids=%s: %s",
            season,
            competition_ids,
            exc,
        )
        raise self.retry(exc=exc)


async def _run_seed(date_str: str, season: str) -> None:
    from sfa.application.use_cases.seed_clubelo import SeedClubEloUseCase
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.providers.clubelo_provider import ClubEloProvider
    from sfa.infrastructure.repositories.team_strength_repository import TeamStrengthRepository
    from sfa.infrastructure.services.elo_calculator import EloCalculatorService

    async with AsyncSessionLocal() as session:
        use_case = SeedClubEloUseCase(
            repo=TeamStrengthRepository(session),
            provider=ClubEloProvider(),
            calculator=EloCalculatorService(),
        )
        result = await use_case.execute(date_str=date_str, season=season)
        if result.status == "completed":
            await session.commit()
        else:
            await session.rollback()
            raise RuntimeError(result.error or "ClubElo seed failed")


async def _run_national_team_seed(
    season: str,
    competition_id: int | None,
    source_url: str | None,
    min_coverage: float,
) -> None:
    from sfa.application.use_cases.seed_national_team_elo import SeedNationalTeamEloUseCase
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.providers.national_team_elo_provider import NationalTeamEloProvider
    from sfa.infrastructure.repositories.team_strength_repository import TeamStrengthRepository
    from sfa.infrastructure.services.elo_calculator import EloCalculatorService

    async with AsyncSessionLocal() as session:
        use_case = SeedNationalTeamEloUseCase(
            repo=TeamStrengthRepository(session),
            provider=NationalTeamEloProvider(),
            calculator=EloCalculatorService(),
        )
        result = await use_case.execute(
            season=season,
            competition_id=competition_id,
            source_url=source_url,
            dry_run=False,
            min_coverage=min_coverage,
        )
        if result.status == "completed":
            await session.commit()
        else:
            await session.rollback()
            raise RuntimeError(result.error or "National-team ELO seed failed")


async def _run_elo_update(season: str, competition_ids: list[int]) -> None:
    from sfa.application.use_cases.calculate_elo_ratings import CalculateEloRatingsUseCase
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.repositories.team_strength_repository import TeamStrengthRepository
    from sfa.infrastructure.services.elo_calculator import EloCalculatorService

    async with AsyncSessionLocal() as session:
        use_case = CalculateEloRatingsUseCase(
            repo=TeamStrengthRepository(session),
            calculator=EloCalculatorService(),
        )
        result = await use_case.execute(
            season=season,
            competition_ids=competition_ids,
            k_factors={},
            default_k=30.0,
        )
        if result.status == "completed":
            await session.commit()
        else:
            await session.rollback()
            raise RuntimeError(result.error or "ELO update failed")
