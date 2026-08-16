from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sfa.celery_app import celery_app

logger = logging.getLogger(__name__)

# Statuses that mean a match is currently in progress
LIVE_STATUSES = {"1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT", "LIVE"}

# Statuses that mean a match is finished — only ingest if within RECENT_WINDOW
FINISHED_STATUSES = {"FT", "AET", "PEN"}

# How long after a match starts we still consider it worth re-ingesting
RECENT_WINDOW = timedelta(hours=4)

# ─── Whitelist de competiciones activas ──────────────────────────────────────
# Solo estos pares (league_id, season) se ingieren automaticamente.
# API-Football representa la temporada de clubes 2026/2027 con season=2026.
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


def _collect_relevant_fixtures(
    fixtures: list[dict],
    known_league_ids: set[int],
) -> dict[tuple[int, int], set[int]]:
    selected: dict[tuple[int, int], set[int]] = {}
    for fixture in fixtures:
        if not _fixture_is_relevant(fixture):
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


@celery_app.task(bind=True, max_retries=1)
def ingest_today_task(self):
    """
    Ingest only the competitions that have live or recently finished fixtures today.
    Runs at the configured beat interval. Costs one API call when nothing is active,
    except around UTC midnight when yesterday is checked as well.
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
    now_utc = datetime.now(timezone.utc)
    dates_to_check = _dates_to_check(now_utc)

    provider = APIFootballProvider(settings.API_FOOTBALL_KEY, settings.API_FOOTBALL_BASE_URL)

    # Around UTC midnight, live American matches can still belong to yesterday's
    # API-Football date, so check both yesterday and today.
    fixtures_today = []
    for fixture_date in dates_to_check:
        data = await provider._get("fixtures", {"date": fixture_date})
        fixtures_today.extend(data.get("response", []))

    league_map = {league.id: league for league in LEAGUES}

    # Collect (league_id, season) pairs that have relevant fixtures right now,
    # but ONLY if they are in the ACTIVE_COMPETITIONS whitelist.
    to_ingest = _collect_relevant_fixtures(
        fixtures_today,
        set(league_map),
    )

    if not to_ingest:
        logger.info(
            "[ingest_today_task] Nothing to ingest for %s "
            "(checked %d fixtures, none live/recent in configured leagues)",
            dates_to_check,
            len(fixtures_today),
        )
        return {"dates": dates_to_check, "ingested": [], "checked": len(fixtures_today)}

    logger.info(
        "[ingest_today_task] Competitions to ingest today (%s): %s",
        dates_to_check,
        {
            league_map[league_id].name: sorted(fixture_ids)
            for (league_id, _season), fixture_ids in to_ingest.items()
        },
    )

    # Ingest sequentially — never in parallel to avoid DB deadlocks
    results = []
    for (league_id, season), fixture_ids in to_ingest.items():
        logger.info(
            "[ingest_today_task] Ingesting %s (league_id=%d season=%d)",
            league_map[league_id].name,
            league_id,
            season,
        )
        result = await _run_ingest_competition(
            league_id,
            season,
            force=True,
            fixture_external_ids=sorted(fixture_ids),
        )
        results.append(result)

    return {"dates": dates_to_check, "ingested": results}
