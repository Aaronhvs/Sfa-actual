from __future__ import annotations

import asyncio

import httpx
from redis.asyncio import Redis

from sfa.celery_app import celery_app
from sfa.core.config import get_settings


@celery_app.task(name="collect_position_lineups_task", soft_time_limit=240, time_limit=300)
def collect_position_lineups_task(season: str | None = None):
    return asyncio.run(_run(season))


async def _run(season: str | None):
    from datetime import datetime, timezone

    from sfa.core.dependencies import (
        get_collect_position_lineups_use_case,
        get_due_position_calendar_scope,
        get_reconcile_position_coverage_use_case,
    )

    settings = get_settings()
    if not settings.POSITION_ACQUISITION_ENABLED:
        return {"state": "disabled", "http_calls": 0}
    now = datetime.now(timezone.utc)
    season = season or str(now.year if now.month >= 7 else now.year - 1)
    redis = Redis.from_url(settings.REDIS_URL)
    try:
        async with httpx.AsyncClient(
            base_url=settings.API_FOOTBALL_BASE_URL,
            headers={"x-apisports-key": settings.API_FOOTBALL_KEY},
            timeout=12.0, follow_redirects=False,
        ) as client:
            use_case = get_collect_position_lineups_use_case(client, redis)
            collection = await use_case.execute(season, min(10, max(1, settings.POSITION_LINEUP_REQUEST_BUDGET)))
            scope = await get_due_position_calendar_scope(season)
            if scope and collection["state"] in {"batch_complete", "no_known_missing_fixtures"}:
                collection["calendar"] = await get_reconcile_position_coverage_use_case(client, redis).execute(
                    scope[0], scope[1], season,
                )
            return collection
    finally:
        await redis.aclose()
