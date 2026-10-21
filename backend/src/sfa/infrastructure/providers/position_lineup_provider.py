from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from weakref import WeakKeyDictionary

import httpx

from sfa.domain.player_positions.ports import LineupEvidenceResponse


class PositionLineupProvider:
    """Direct backend HTTP transport: no retries, no SSH, no account data export."""

    _last_request: WeakKeyDictionary = WeakKeyDictionary()

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def status(self) -> LineupEvidenceResponse:
        return await self._request(None)

    async def fetch_lineups(self, fixture_id: int) -> LineupEvidenceResponse:
        if type(fixture_id) is not int or fixture_id <= 0:
            raise ValueError("Invalid fixture identity")
        return await self._request(fixture_id)

    async def fetch_calendar(self, league_id: int, season: str) -> LineupEvidenceResponse:
        if type(league_id) is not int or league_id <= 0 or not season.isdigit() or len(season) != 4:
            raise ValueError("Invalid competition/season")
        return await self._request(None, endpoint="/fixtures", params={"league": league_id, "season": season})

    async def _request(
        self, fixture_id: int | None, *, endpoint: str | None = None, params: dict | None = None,
    ) -> LineupEvidenceResponse:
        # Collector and calendar adapters can share a client. Keep their combined
        # pace bounded too; this is pacing, never an implicit HTTP retry.
        elapsed = time.monotonic() - self._last_request.get(self._client, 0.0)
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        self._last_request[self._client] = time.monotonic()
        fetched_at = datetime.now(timezone.utc).isoformat()
        try:
            response = await self._client.get(endpoint or ("/fixtures/lineups" if fixture_id else "/status"),
                                              params=params or ({"fixture": fixture_id} if fixture_id else None))
        except httpx.HTTPError as exc:
            return LineupEvidenceResponse(fixture_id, 0, "{}", fetched_at, None, None, None, type(exc).__name__)

        def quota(header):
            value = response.headers.get(header, "")
            return int(value) if value.isdigit() else None

        body = response.text
        if fixture_id is None and endpoint is None:
            try:
                payload = response.json()
                account = payload.get("response") or {}
                body = json.dumps({"errors": bool(payload.get("errors")),
                                   "active": (account.get("subscription") or {}).get("active"),
                                   "requests": account.get("requests")})
            except (ValueError, AttributeError):
                body = '{"errors":true}'
        return LineupEvidenceResponse(
            fixture_id, response.status_code, body, fetched_at,
            quota("x-ratelimit-requests-remaining"), quota("x-ratelimit-remaining"), quota("x-ratelimit-limit"),
        )
