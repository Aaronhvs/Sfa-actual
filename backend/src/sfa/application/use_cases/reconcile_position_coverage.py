from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sfa.domain.player_positions.ports import PositionCalendarCoverageState, PositionCalendarProvider


class ReconcilePositionCoverageUseCase:
    """Reconcile provider season inventory against retained starting elevens.

    API-Football fixtures returns the whole league/season in one page. Explicit
    paging proof is mandatory; a changed/multi-page contract remains incomplete
    instead of guessing a page parameter unsupported by this endpoint.
    """

    def __init__(self, provider: PositionCalendarProvider, state: PositionCalendarCoverageState,
                 daily_reserve: int = 100) -> None:
        self._provider = provider
        self._state = state
        self._reserve = max(100, daily_reserve)

    async def execute(self, competition_id: int, league_id: int, season: str) -> dict:
        if competition_id <= 0 or league_id <= 0 or not season.isdigit() or len(season) != 4:
            raise ValueError("Invalid competition identity or season")
        if not await self._state.acquire():
            return {"state": "lease_busy", "http_calls": 0}
        try:
            quota = await self._provider.status()
            if (quota.http_status != 200 or quota.transport_error or quota.daily_remaining is None
                    or quota.daily_remaining <= self._reserve or quota.minute_remaining is None
                    or quota.minute_remaining <= 2):
                return {"state": "quota_unavailable", "http_calls": 1}
            account = json.loads(quota.body)
            if account.get("errors") or account.get("active") is not True:
                return {"state": "subscription_unavailable", "http_calls": 1}
            if not await self._state.owns_lease():
                return {"state": "lease_lost", "http_calls": 1}
            response = await self._provider.fetch_calendar(league_id, season)
            proof = {"competition_id": competition_id, "league_id": league_id, "season": season,
                     "fetched_at": response.fetched_at,
                     "payload_sha256": hashlib.sha256(response.body.encode()).hexdigest(),
                     "raw_body": response.body, "http_status": response.http_status,
                     "transport_error": response.transport_error, "habitual_role_coverage": "unknown"}
            try:
                payload = json.loads(response.body)
                rows = payload.get("response")
                paging = payload.get("paging") or {}
                parameters = payload.get("parameters") or {}
                valid = (response.http_status == 200 and not response.transport_error and not payload.get("errors")
                         and isinstance(rows, list) and payload.get("results") == len(rows)
                         and paging.get("current") == paging.get("total") == 1
                         and str(parameters.get("league")) == str(league_id)
                         and str(parameters.get("season")) == season)
                inventory = {row["external_id"]: row for row in json.loads(
                    await self._state.inventory(competition_id, season)
                )}
                completed, missing, mismatched, without_xi = [], [], [], []
                identities = set()
                now = datetime.now(timezone.utc)
                for row in rows if valid else []:
                    fixture = row["fixture"]
                    external_id = fixture["id"]
                    if (type(external_id) is not int or external_id <= 0 or external_id in identities
                            or row["league"]["id"] != league_id or str(row["league"]["season"]) != season):
                        valid = False
                        break
                    identities.add(external_id)
                    if fixture["status"]["short"] not in {"FT", "AET", "PEN"}:
                        continue
                    if datetime.fromisoformat(fixture["date"].replace("Z", "+00:00")) > now:
                        valid = False
                        break
                    completed.append(external_id)
                    stored = inventory.get(external_id)
                    if stored is None:
                        missing.append(external_id)
                    elif (stored["home_team_external_id"], stored["away_team_external_id"]) != (
                            row["teams"]["home"]["id"], row["teams"]["away"]["id"]):
                        mismatched.append(external_id)
                    elif not stored["both_starting_elevens"]:
                        without_xi.append(external_id)
                local_completed = {i for i, item in inventory.items() if item["status"] in {"FT", "AET", "PEN"}}
                unlisted = sorted(local_completed - set(completed))
                proof.update(calendar_reconciled=bool(valid), completed_fixture_ids=sorted(completed),
                             missing_ingestion_ids=sorted(missing), identity_mismatch_ids=sorted(mismatched),
                             missing_lineup_ids=sorted(without_xi), local_unlisted_ids=unlisted,
                             empty_scope=not bool(completed))
                # Empty scope does not establish a starter denominator for any player.
                status = ("complete" if (valid and completed and not any((missing, mismatched, without_xi, unlisted)))
                          else "partial" if valid else "invalid")
            except (ValueError, TypeError, KeyError, AttributeError):
                proof["calendar_reconciled"] = False
                status = "invalid"
            await self._state.record_calendar(
                f"calendar:{league_id}:{season}", json.dumps(proof, sort_keys=True), status,
            )
            return {key: value for key, value in {**proof, "state": status, "http_calls": 2}.items()
                    if key != "raw_body"}
        finally:
            await self._state.release()
