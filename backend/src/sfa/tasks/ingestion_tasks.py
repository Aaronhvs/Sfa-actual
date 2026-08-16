from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING

from sfa.celery_app import celery_app

if TYPE_CHECKING:
    from sfa.application.use_cases.ingest_competition import LeagueConfig

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def ingest_competition_task(
    self,
    league_id: int,
    season: int,
    force: bool = False,
    fixture_external_ids: list[int] | None = None,
):
    """Ingest a single league. Thin sync to async wrapper."""
    try:
        return asyncio.run(
            _run_ingest_competition(
                league_id,
                season,
                force,
                fixture_external_ids,
            )
        )
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=1)
def ingest_all_competitions_task(
    self, season: int, force: bool = False,
):
    """Ingest all configured leagues."""
    try:
        return asyncio.run(_run_ingest_all(season, force))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _get_competition_id_by_league(league: LeagueConfig) -> int | None:
    from sqlalchemy import select

    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.models.competitions.models import Competition

    async with AsyncSessionLocal() as session:
        return await session.scalar(
            select(Competition.id).where(Competition.name == league.name)
        )


async def _get_competition_ids_for_kind(
    season: int, participant_kind: str
) -> list[int]:
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.repositories.team_strength_repository import TeamStrengthRepository

    async with AsyncSessionLocal() as session:
        return await TeamStrengthRepository(session).get_competition_ids_for_participant_kind(
            str(season), participant_kind
        )


async def _already_completed(league: LeagueConfig, season: int) -> bool:
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.models.enums import IngestionStatus
    from sfa.infrastructure.repositories.ingestion_repository import IngestionRepository

    competition_id = await _get_competition_id_by_league(league)
    if competition_id is None:
        return False

    async with AsyncSessionLocal() as session:
        repo = IngestionRepository(session)
        log = await repo.get_last_ingestion_log(competition_id, str(season))
    return log is not None and log.status == IngestionStatus.COMPLETED


def _skipped_result(league_id: int, season: int) -> dict[str, object]:
    return {
        "skipped": True,
        "reason": "already_completed",
        "league_id": league_id,
        "season": season,
    }


def _serialize_result(result):
    return asdict(result) if is_dataclass(result) else result


async def _run_ingest_competition(
    league_id: int,
    season: int,
    force: bool = False,
    fixture_external_ids: list[int] | None = None,
):
    from sfa.application.use_cases.ingest_competition import (
        LEAGUES,
        IngestCompetitionUseCase,
    )
    from sfa.core.config import get_settings
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.providers.api_football import APIFootballProvider
    from sfa.infrastructure.repositories.ingestion_repository import IngestionRepository

    league = next((item for item in LEAGUES if item.id == league_id), None)
    if league is None:
        raise ValueError(f"League not found: {league_id}")

    if not force and await _already_completed(league, season):
        logger.info(
            "[ingest_competition_task] Skipping league_id=%s season=%s — already completed",
            league_id,
            season,
        )
        return _skipped_result(league_id, season)

    settings = get_settings()
    provider = APIFootballProvider(
        settings.API_FOOTBALL_KEY,
        settings.API_FOOTBALL_BASE_URL,
    )

    async with AsyncSessionLocal() as session:
        repo = IngestionRepository(session)
        use_case = IngestCompetitionUseCase(provider, repo)
        result = await use_case.execute(
            league,
            season,
            target_fixture_external_ids=(
                set(fixture_external_ids)
                if fixture_external_ids is not None
                else None
            ),
        )
        await session.commit()

    competition_id = await _get_competition_id_by_league(league)
    if competition_id is None:
        await _trigger_recalculation(season)
    else:
        await _trigger_recalculation_after_elo_pools(
            season,
            club_competition_ids=(
                await _get_competition_ids_for_kind(season, "club")
                if league.participant_kind == "club"
                else []
            ),
            national_competition_ids=(
                [competition_id]
                if league.participant_kind == "national_team"
                else []
            ),
        )

    return _serialize_result(result)


async def _run_ingest_all(season: int, force: bool = False):
    from sfa.application.use_cases.ingest_competition import (
        LEAGUES,
        IngestCompetitionUseCase,
    )
    from sfa.core.config import get_settings
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.providers.api_football import APIFootballProvider
    from sfa.infrastructure.repositories.ingestion_repository import IngestionRepository

    settings = get_settings()
    provider = APIFootballProvider(
        settings.API_FOOTBALL_KEY,
        settings.API_FOOTBALL_BASE_URL,
    )
    results = []
    national_competition_ids: set[int] = set()
    club_competition_ids: set[int] = set()

    async with AsyncSessionLocal() as session:
        repo = IngestionRepository(session)
        use_case = IngestCompetitionUseCase(provider, repo)
        for league in LEAGUES:
            if provider.requests_used >= 7000:
                break
            if not force and await _already_completed(league, season):
                logger.info(
                    "[ingest_competition_task] Skipping league_id=%s season=%s — already completed",
                    league.id,
                    season,
                )
                results.append(_skipped_result(league.id, season))
                continue
            results.append(_serialize_result(await use_case.execute(league, season)))
            await session.commit()
            competition_id = await _get_competition_id_by_league(league)
            if competition_id is not None and league.participant_kind == "national_team":
                national_competition_ids.add(competition_id)
            elif competition_id is not None:
                club_competition_ids.add(competition_id)

    if national_competition_ids or club_competition_ids:
        await _trigger_recalculation_after_elo_pools(
            season,
            club_competition_ids=(
                await _get_competition_ids_for_kind(season, "club")
                if club_competition_ids
                else []
            ),
            national_competition_ids=sorted(national_competition_ids),
        )
    else:
        await _trigger_recalculation(season)
    return results


async def _trigger_recalculation(season: int) -> None:
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.repositories.scoring_rules_version_repository import ScoringRulesVersionRepository

    async with AsyncSessionLocal() as ver_session:
        active_version = await ScoringRulesVersionRepository(ver_session).get_active_version()

    if active_version is None:
        logger.error("[ingestion] No active scoring rules version found — skipping recalculation")
        return

    from sfa.tasks.run_full_recalculation_task import run_full_recalculation_task
    run_full_recalculation_task.delay(
        rules_version_id=active_version.id,
        season=str(season),
        force_recalculate=True,
    )
    logger.info(
        "[ingestion] Queued recalculation rules_version_id=%d season=%s",
        active_version.id, season,
    )


async def _trigger_recalculation_after_national_team_elo(
    season: int,
    competition_ids: list[int],
) -> None:
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.repositories.scoring_rules_version_repository import ScoringRulesVersionRepository

    async with AsyncSessionLocal() as ver_session:
        active_version = await ScoringRulesVersionRepository(ver_session).get_active_version()

    if active_version is None:
        logger.error("[ingestion] No active scoring rules version found — skipping national-team ELO recalculation")
        return

    from sfa.tasks.elo_tasks import apply_elo_update_then_recalculate_task
    apply_elo_update_then_recalculate_task.delay(
        str(season),
        competition_ids,
        active_version.id,
    )
    logger.info(
        "[ingestion] Queued national-team ELO + recalculation "
        "rules_version_id=%d season=%s competition_ids=%s",
        active_version.id,
        season,
        competition_ids,
    )


async def _trigger_recalculation_after_elo_pools(
    season: int,
    club_competition_ids: list[int],
    national_competition_ids: list[int],
) -> None:
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.repositories.scoring_rules_version_repository import ScoringRulesVersionRepository

    async with AsyncSessionLocal() as ver_session:
        active_version = await ScoringRulesVersionRepository(ver_session).get_active_version()

    if active_version is None:
        logger.error("[ingestion] No active scoring rules version found - skipping ELO/scoring")
        return

    from sfa.tasks.elo_tasks import apply_elo_pools_then_recalculate_task

    apply_elo_pools_then_recalculate_task.delay(
        str(season),
        active_version.id,
        club_competition_ids,
        national_competition_ids,
    )
    logger.info(
        "[ingestion] Queued ELO pools + recalculation rules_version_id=%d "
        "season=%s clubs=%s national=%s",
        active_version.id,
        season,
        club_competition_ids,
        national_competition_ids,
    )
