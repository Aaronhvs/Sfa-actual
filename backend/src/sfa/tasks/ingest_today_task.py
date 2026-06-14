from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from sfa.celery_app import celery_app

logger = logging.getLogger(__name__)

# Statuses that mean a match is currently in progress
LIVE_STATUSES = {"1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT", "LIVE"}

# Statuses that mean a match is finished — only ingest if within RECENT_WINDOW
FINISHED_STATUSES = {"FT", "AET", "PEN"}

# How long after a match starts we still consider it worth re-ingesting
RECENT_WINDOW = timedelta(hours=4)


def _fixture_is_relevant(fixture: dict) -> bool:
    """Return True if this fixture has live or recently finished data worth ingesting."""
    status = fixture.get("fixture", {}).get("status", {}).get("short", "")
    if status in LIVE_STATUSES:
        return True
    if status in FINISHED_STATUSES:
        match_date_str = fixture.get("fixture", {}).get("date", "")
        try:
            match_dt = datetime.fromisoformat(match_date_str.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) - match_dt < RECENT_WINDOW
        except (ValueError, TypeError):
            return True
    return False


@celery_app.task(bind=True, max_retries=1)
def ingest_today_task(self):
    """
    Ingest only the competitions that have live or recently finished fixtures today.
    Runs every 30 minutes via beat schedule. Costs 1 API call when nothing is active.
    """
    try:
        return asyncio.run(_run_ingest_today())
    except Exception as exc:
        raise self.retry(exc=exc)


async def _run_ingest_today() -> dict:
    from sfa.application.use_cases.ingest_competition import LEAGUES
    from sfa.core.config import get_settings
    from sfa.infrastructure.providers.api_football import APIFootballProvider
    from sfa.tasks.ingestion_tasks import _run_ingest_competition

    settings = get_settings()
    today = date.today().strftime("%Y-%m-%d")

    provider = APIFootballProvider(settings.API_FOOTBALL_KEY, settings.API_FOOTBALL_BASE_URL)

    # 1 API call: all fixtures for today
    data = await provider._get("fixtures", {"date": today})
    fixtures_today = data.get("response", [])

    league_map = {league.id: league for league in LEAGUES}

    # Collect (league_id, season) pairs that have relevant fixtures right now
    to_ingest: dict[int, int] = {}  # league_id → season
    for fixture in fixtures_today:
        if not _fixture_is_relevant(fixture):
            continue
        league_id = fixture["league"]["id"]
        season = fixture["league"]["season"]
        if league_id in league_map and league_id not in to_ingest:
            to_ingest[league_id] = season

    if not to_ingest:
        logger.info(
            "[ingest_today_task] Nothing to ingest for %s "
            "(checked %d fixtures, none live/recent in configured leagues)",
            today,
            len(fixtures_today),
        )
        return {"date": today, "ingested": [], "checked": len(fixtures_today)}

    logger.info(
        "[ingest_today_task] Competitions to ingest today (%s): %s",
        today,
        {league_map[lid].name: s for lid, s in to_ingest.items()},
    )

    # Ingest sequentially — never in parallel to avoid DB deadlocks
    results = []
    for league_id, season in to_ingest.items():
        logger.info(
            "[ingest_today_task] Ingesting %s (league_id=%d season=%d)",
            league_map[league_id].name,
            league_id,
            season,
        )
        result = await _run_ingest_competition(league_id, season, force=True)
        results.append(result)

    return {"date": today, "ingested": results}
