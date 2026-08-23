from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

from sfa.celery_app import celery_app
from sfa.domain.ingestion_ports import ProviderDailyQuotaExceededError

logger = logging.getLogger(__name__)

LIVE_STATUSES = {"1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT", "LIVE"}
FINISHED_STATUSES = {"FT", "AET", "PEN"}
RECENT_WINDOW = timedelta(hours=4)
INGESTION_LOCK_KEY = 42_026_001

# API-Football represents club season 2026/2027 as season=2026.
ACTIVE_COMPETITIONS: frozenset[tuple[int, int]] = frozenset({
    (531, 2026),  # UEFA Super Cup
    (528, 2026),  # Community Shield
    (140, 2026),  # La Liga
    (39, 2026),   # Premier League
    (78, 2026),   # Bundesliga
    (135, 2026),  # Serie A
    (61, 2026),   # Ligue 1
    (2, 2026),    # Champions League
    (3, 2026),    # Europa League
    (848, 2026),  # Conference League
    (143, 2026),  # Copa del Rey
    (556, 2026),  # Supercopa de Espana
    (45, 2026),   # FA Cup
    (48, 2026),   # EFL Cup
    (81, 2026),   # DFB-Pokal
    (529, 2026),  # DFL-Supercup
    (137, 2026),  # Coppa Italia
    (547, 2026),  # Supercoppa Italiana
    (66, 2026),   # Coupe de France
    (526, 2026),  # Trophee des Champions
})


def _fixture_is_relevant(
    fixture: dict,
    *,
    include_all_finished: bool = False,
) -> bool:
    status = fixture.get("fixture", {}).get("status", {}).get("short", "")
    if status in LIVE_STATUSES:
        return True
    if status not in FINISHED_STATUSES:
        return False
    if include_all_finished:
        return True

    match_date_str = fixture.get("fixture", {}).get("date", "")
    try:
        match_dt = datetime.fromisoformat(match_date_str.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) - match_dt < RECENT_WINDOW
    except (ValueError, TypeError):
        return True


def _collect_relevant_fixtures(
    fixtures: list[dict],
    known_league_ids: set[int],
    *,
    include_all_finished: bool = False,
) -> dict[tuple[int, int], set[int]]:
    selected: dict[tuple[int, int], set[int]] = {}
    for fixture in fixtures:
        if not _fixture_is_relevant(
            fixture,
            include_all_finished=include_all_finished,
        ):
            continue
        league = fixture.get("league", {})
        fixture_data = fixture.get("fixture", {})
        league_id = league.get("id")
        season = league.get("season")
        fixture_id = fixture_data.get("id")
        if not all(isinstance(value, int) for value in (league_id, season, fixture_id)):
            continue
        pair = (league_id, season)
        if pair not in ACTIVE_COMPETITIONS or league_id not in known_league_ids:
            continue
        selected.setdefault(pair, set()).add(fixture_id)
    return selected


def _dates_to_check(now_utc: datetime) -> list[str]:
    dates = [now_utc.date().isoformat()]
    if now_utc.hour < 4:
        dates.insert(0, (now_utc - timedelta(days=1)).date().isoformat())
    return dates


@celery_app.task(bind=True, max_retries=1, default_retry_delay=180)
def ingest_today_task(self):
    """Ingest live/recent fixtures and consolidate ELO/scoring once per cycle."""
    try:
        return asyncio.run(_run_ingest_today())
    except ProviderDailyQuotaExceededError as exc:
        logger.warning("[ingest_today_task] Daily provider quota exhausted: %s", exc)
        return {"status": "quota_exhausted", "error": str(exc)}
    except Exception as exc:
        raise self.retry(exc=exc)


async def _run_ingest_today() -> dict:
    now_utc = datetime.now(timezone.utc)
    return await _run_with_ingestion_lock(
        "live",
        lambda: _run_ingest_dates(
            _dates_to_check(now_utc),
            include_all_finished=False,
            cycle_name="live",
        ),
    )


async def _run_with_ingestion_lock(
    cycle_name: str,
    runner: Callable[[], Awaitable[dict]],
) -> dict:
    from sqlalchemy import text

    from sfa.infrastructure.database import AsyncSessionLocal

    async with AsyncSessionLocal() as lock_session:
        acquired = await lock_session.scalar(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": INGESTION_LOCK_KEY},
        )
        if not acquired:
            logger.info("[%s_ingestion_task] Skipping: another cycle is running", cycle_name)
            return {"status": "already_running", "cycle": cycle_name}

        try:
            return await runner()
        finally:
            await lock_session.execute(
                text("SELECT pg_advisory_unlock(:key)"),
                {"key": INGESTION_LOCK_KEY},
            )
            await lock_session.commit()


async def _run_ingest_dates(
    dates_to_check: list[str],
    *,
    include_all_finished: bool,
    cycle_name: str,
) -> dict:
    from sfa.application.use_cases.ingest_competition import LEAGUES
    from sfa.core.config import get_settings
    from sfa.infrastructure.providers.api_football import APIFootballProvider
    from sfa.tasks.ingestion_tasks import (
        _run_ingest_competition,
        _trigger_recalculation_for_leagues,
    )

    settings = get_settings()
    provider = APIFootballProvider(
        settings.API_FOOTBALL_KEY,
        settings.API_FOOTBALL_BASE_URL,
    )
    fixtures: list[dict] = []
    completed_by_season: dict[int, list] = {}
    results: list[dict] = []
    quota_error: str | None = None

    try:
        for fixture_date in dates_to_check:
            data = await provider._get("fixtures", {"date": fixture_date})
            fixtures.extend(data.get("response", []))

        league_map = {league.id: league for league in LEAGUES}
        to_ingest = _collect_relevant_fixtures(
            fixtures,
            set(league_map),
            include_all_finished=include_all_finished,
        )

        if not to_ingest:
            logger.info(
                "[%s_ingestion_task] Nothing to ingest for %s (checked=%d)",
                cycle_name,
                dates_to_check,
                len(fixtures),
            )
            return {
                "status": "completed",
                "cycle": cycle_name,
                "dates": dates_to_check,
                "ingested": [],
                "checked": len(fixtures),
                "recalculation_queued": False,
            }

        logger.info(
            "[%s_ingestion_task] Selected competitions for %s: %s",
            cycle_name,
            dates_to_check,
            {
                league_map[league_id].name: sorted(fixture_ids)
                for (league_id, _season), fixture_ids in to_ingest.items()
            },
        )

        for (league_id, season), fixture_ids in to_ingest.items():
            league = league_map[league_id]
            logger.info(
                "[%s_ingestion_task] Ingesting %s season=%d fixtures=%s",
                cycle_name,
                league.name,
                season,
                sorted(fixture_ids),
            )
            try:
                result = await _run_ingest_competition(
                    league_id,
                    season,
                    force=True,
                    fixture_external_ids=sorted(fixture_ids),
                    enqueue_recalculation=False,
                )
            except ProviderDailyQuotaExceededError as exc:
                quota_error = str(exc)
                logger.warning(
                    "[%s_ingestion_task] Daily quota exhausted; stopping batch: %s",
                    cycle_name,
                    exc,
                )
                break

            results.append(result)
            if result.get("status") == "completed":
                completed_by_season.setdefault(season, []).append(league)
    except ProviderDailyQuotaExceededError as exc:
        quota_error = str(exc)
        logger.warning(
            "[%s_ingestion_task] Daily quota exhausted during discovery: %s",
            cycle_name,
            exc,
        )
    finally:
        await provider.close()

    recalculation_queued = False
    for season, leagues in completed_by_season.items():
        queued = await _trigger_recalculation_for_leagues(
            season,
            leagues,
            force_recalculate=False,
        )
        recalculation_queued = recalculation_queued or queued

    return {
        "status": "quota_exhausted" if quota_error else "completed",
        "cycle": cycle_name,
        "dates": dates_to_check,
        "ingested": results,
        "checked": len(fixtures),
        "quota_exhausted": quota_error is not None,
        "error": quota_error,
        "recalculation_queued": recalculation_queued,
    }
