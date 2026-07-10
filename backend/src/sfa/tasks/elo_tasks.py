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


@celery_app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=120,
    name="sfa.tasks.apply_elo_update_then_recalculate_task",
)
def apply_elo_update_then_recalculate_task(
    self,
    season: str,
    competition_ids: list[int],
    rules_version_id: int,
    default_k: float | None = None,
    source: str = "national_elo_v1",
):
    """Update national-team ELO, then rebuild scores so M1 uses fresh strengths."""
    try:
        asyncio.run(
            _run_elo_update_then_recalculate(
                season=season,
                competition_ids=competition_ids,
                rules_version_id=rules_version_id,
                default_k=default_k,
                source=source,
            )
        )
    except Exception as exc:
        logger.error(
            "[apply_elo_update_then_recalculate_task] Failed season=%s "
            "competition_ids=%s rules_version_id=%d: %s",
            season,
            competition_ids,
            rules_version_id,
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


async def _run_elo_update(
    season: str,
    competition_ids: list[int],
    default_k: float = 30.0,
    source: str = "elo_v1",
    use_seed_baseline: bool = False,
    require_seed_baseline: bool = False,
) -> None:
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
            default_k=default_k,
            source=source,
            use_seed_baseline=use_seed_baseline,
            require_seed_baseline=require_seed_baseline,
        )
        if result.status == "completed":
            await session.commit()
        else:
            await session.rollback()
            raise RuntimeError(result.error or "ELO update failed")


async def _run_elo_update_then_recalculate(
    season: str,
    competition_ids: list[int],
    rules_version_id: int,
    default_k: float | None,
    source: str,
) -> None:
    from sqlalchemy import text

    from sfa.core.config import get_settings
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.tasks.run_full_recalculation_task import _run as _run_full_recalculation

    settings = get_settings()
    resolved_k = (
        settings.NATIONAL_TEAM_ELO_DEFAULT_K
        if default_k is None
        else default_k
    )
    logger.info(
        "[apply_elo_update_then_recalculate_task] START season=%s "
        "competition_ids=%s rules_version_id=%d k=%s source=%s",
        season,
        competition_ids,
        rules_version_id,
        resolved_k,
        source,
    )
    lock_key = _national_elo_lock_key(season, competition_ids)
    async with AsyncSessionLocal() as lock_session:
        await lock_session.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_key})
        try:
            await _run_elo_update(
                season=season,
                competition_ids=competition_ids,
                default_k=resolved_k,
                source=source,
                use_seed_baseline=True,
                require_seed_baseline=True,
            )
            await _run_full_recalculation(
                rules_version_id=rules_version_id,
                season=season,
                force_recalculate=True,
                infer_achievements=True,
            )
        finally:
            await lock_session.execute(
                text("SELECT pg_advisory_unlock(:key)"),
                {"key": lock_key},
            )
            await lock_session.commit()
    logger.info(
        "[apply_elo_update_then_recalculate_task] DONE season=%s "
        "competition_ids=%s rules_version_id=%d",
        season,
        competition_ids,
        rules_version_id,
    )


def _national_elo_lock_key(season: str, competition_ids: list[int]) -> int:
    scope = f"{season}:{','.join(str(item) for item in sorted(competition_ids))}"
    return 40_000_000 + (sum(ord(char) for char in scope) % 10_000_000)
