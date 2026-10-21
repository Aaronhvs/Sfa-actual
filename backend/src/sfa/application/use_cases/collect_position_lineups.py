from __future__ import annotations

import json
from dataclasses import asdict

from sfa.domain.player_positions.ports import (
    LineupEvidenceProvider,
    LineupEvidenceResponse,
    PositionEvidenceRecorder,
    PositionLineupCollectionState,
)


def _error(response: LineupEvidenceResponse) -> str | None:
    if response.transport_error:
        return response.transport_error
    if response.http_status != 200:
        return f"http_{response.http_status}"
    try:
        payload = json.loads(response.body)
    except ValueError:
        return "invalid_json"
    if not isinstance(payload, dict):
        return "invalid_schema"
    return "provider_error" if payload.get("errors") else None


class CollectPositionLineupsUseCase:
    """Bounded acquisition independent of site visits, without publication ports."""

    def __init__(
        self, provider: LineupEvidenceProvider, recorder: PositionEvidenceRecorder,
        state: PositionLineupCollectionState, *, daily_reserve: int = 100,
    ) -> None:
        self._provider = provider
        self._recorder = recorder
        self._state = state
        self._reserve = max(100, daily_reserve)

    async def execute(self, season: str, max_fixtures: int = 10) -> dict:
        if not season.isdigit() or len(season) != 4 or not 1 <= max_fixtures <= 10:
            raise ValueError("Expected four-digit season and batch of 1..10")
        report = {"season": season, "http_calls": 0, "captured": [], "state": "lease_busy"}
        if not await self._state.acquire():
            return report
        try:
            pending = await self._state.pending(season, max_fixtures)
            if not pending:
                return {**report, "state": "no_known_missing_fixtures", "calendar_coverage": "unknown"}
            await self._state.checkpoint(None, "attempt_started", "{}")
            quota = await self._provider.status()
            report["http_calls"] += 1
            await self._state.checkpoint(None, "response", json.dumps(asdict(quota)))
            error = _error(quota)
            if error or json.loads(quota.body).get("active") is not True:
                return {**report, "state": error or "subscription_inactive"}
            for fixture_id in pending:
                if not await self._state.owns_lease():
                    return {**report, "state": "lease_lost"}
                if quota.daily_remaining is None or quota.daily_remaining <= self._reserve:
                    return {**report, "state": "daily_quota_reserve"}
                if quota.minute_remaining is None or quota.minute_remaining <= 2:
                    return {**report, "state": "minute_quota_reserve"}
                # Persist the attempt before HTTP. A crash leaves a bounded cooldown,
                # rather than an invisible retry loop against the provider account.
                await self._state.checkpoint(fixture_id, "attempt_started", "{}")
                response = await self._provider.fetch_lineups(fixture_id)
                report["http_calls"] += 1
                await self._state.checkpoint(fixture_id, "response", json.dumps(asdict(response)))
                error = _error(response)
                if response.fixture_id != fixture_id:
                    error = "fixture_identity_mismatch"
                if error:
                    return {**report, "state": error}
                if not await self._state.owns_lease():
                    return {**report, "state": "lease_lost_after_response"}
                capture = await self._recorder.execute(
                    fixture_id, response.body, "api-football-v3/fixtures/lineups", response.fetched_at,
                )
                report["captured"].append(asdict(capture))
                if capture.status != "recorded":
                    return {**report, "state": capture.status}
                quota = response
            return {**report, "state": "batch_complete", "calendar_coverage": "unknown"}
        finally:
            await self._state.release()
