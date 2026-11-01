"""Teams with a match in progress, published by the live ingestion cycle.

The live cycle already fetches today's fixtures every few minutes; it stores the
in-play teams here so the API can expose them without extra provider calls.
"""
from __future__ import annotations

import json
import time

import redis.asyncio as aioredis

LIVE_TEAMS_KEY = "sfa:live_teams"
# Slightly longer than two ingestion intervals, so one skipped cycle does not
# blank the indicator, while a stale snapshot still expires on its own.
LIVE_TEAMS_TTL_SECONDS = 25 * 60
# A match never stays "in play" this long after kickoff; guards stale snapshots.
MAX_MATCH_AGE_SECONDS = 4 * 60 * 60

LIVE_STATUSES = {"1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT", "LIVE"}


def live_team_ids(fixtures: list[dict], known_league_ids: set[int]) -> dict[int, int]:
    """Map team external id -> kickoff unix timestamp for in-play fixtures."""
    teams: dict[int, int] = {}
    for fixture in fixtures:
        fixture_data = fixture.get("fixture", {})
        if fixture_data.get("status", {}).get("short") not in LIVE_STATUSES:
            continue
        if fixture.get("league", {}).get("id") not in known_league_ids:
            continue
        kickoff = fixture_data.get("timestamp")
        if not isinstance(kickoff, int):
            continue
        for side in ("home", "away"):
            team_id = fixture.get("teams", {}).get(side, {}).get("id")
            if isinstance(team_id, int):
                teams[team_id] = kickoff
    return teams


async def publish_live_teams(redis_url: str, teams: dict[int, int]) -> None:
    client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        payload = json.dumps({"updated_at": int(time.time()), "teams": teams})
        await client.set(LIVE_TEAMS_KEY, payload, ex=LIVE_TEAMS_TTL_SECONDS)
    finally:
        await client.aclose()


async def read_live_teams(client: aioredis.Redis) -> tuple[list[int], int | None]:
    raw = await client.get(LIVE_TEAMS_KEY)
    if not raw:
        return [], None
    data = json.loads(raw)
    now = int(time.time())
    team_ids = sorted(
        int(team_id)
        for team_id, kickoff in data.get("teams", {}).items()
        if now - int(kickoff) < MAX_MATCH_AGE_SECONDS
    )
    return team_ids, data.get("updated_at")
