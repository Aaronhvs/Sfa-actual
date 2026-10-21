import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime

from sfa.domain.player_positions.ports import (
    LineupEvidenceArchive,
    LineupEvidenceProvider,
    LineupEvidenceResponse,
    PositionAuditSnapshotSource,
)


@dataclass(frozen=True)
class RecoverMissingLineupsResult:
    summary_json: str


def _decode(response: LineupEvidenceResponse) -> tuple[dict, str | None]:
    if response.transport_error or response.http_status != 200:
        return {}, response.transport_error or f"http_{response.http_status}"
    try:
        data = json.loads(response.body)
    except (ValueError, TypeError):
        return {}, "unsupported_schema"
    if not isinstance(data, dict):
        return {}, "unsupported_schema"
    if data.get("errors"):
        return data, "provider_error"
    return data, None


def _normalize(response: LineupEvidenceResponse, fixture: dict) -> tuple[dict | None, str]:
    data, error = _decode(response)
    if error:
        return None, error
    rows = data.get("response")
    if rows == []:
        return None, "provider_empty"
    expected = {fixture["home_team_external_id"], fixture["away_team_external_id"]}
    parameters = data.get("parameters")
    if (not isinstance(parameters, dict) or str(parameters.get("fixture")) != str(fixture["external_id"])
            or not isinstance(rows, list) or len(rows) != 2 or any(not isinstance(row, dict) for row in rows)
            or any(not isinstance(row.get("team"), dict) for row in rows)
            or {row.get("team", {}).get("id") for row in rows} != expected):
        return None, "unsupported_schema"
    lineups = []
    for row in rows:
        if not isinstance(row.get("startXI"), list) or not isinstance(row.get("substitutes"), list):
            return None, "unsupported_schema"
        normalized = {"team": {"external_id": row["team"]["id"], "name": row["team"].get("name", "")},
                      "formation": row.get("formation")}
        for source, target in (("startXI", "start_xi"), ("substitutes", "substitutes")):
            slots = []
            for entry in row[source]:
                player = entry.get("player") if isinstance(entry, dict) else None
                if not isinstance(player, dict):
                    return None, "unsupported_schema"
                slots.append({"external_id": player.get("id"), "name": player.get("name", ""),
                              "position": player.get("pos"), "grid": player.get("grid")})
            normalized[target] = slots
        lineups.append(normalized)
    summary = {"external_id": fixture["external_id"], "played_at": fixture["played_at"],
               "home_team": {"external_id": fixture["home_team_external_id"]},
               "away_team": {"external_id": fixture["away_team_external_id"]}}
    return {"key": f"fixture:api:supplement:v2:{fixture['external_id']}",
            "payload": {"fixture": summary, "lineups": lineups},
            "source": "api-football-v3/fixtures/lineups", "fetched_at": response.fetched_at,
            "sha256": hashlib.sha256(response.body.encode()).hexdigest()}, "recovered"


def _compatible_partial(previous: dict, recovered: dict) -> bool:
    """Absence can be supplemented; conflicting preserved assertions cannot."""
    newer = {lineup["team"]["external_id"]: lineup for lineup in recovered["payload"]["lineups"]}
    for old in previous["payload"].get("lineups", []):
        team = old.get("team", {}).get("external_id")
        if team not in newer:
            return False
        new = newer[team]
        if old.get("formation") and old["formation"] != new.get("formation"):
            return False
        players = {player["external_id"]: player for player in new["start_xi"]}
        for player in old.get("start_xi", []):
            candidate = players.get(player.get("external_id"))
            if candidate is None or any(player.get(key) is not None and player[key] != candidate.get(key)
                                        for key in ("grid", "position")):
                return False
    return True


class RecoverMissingLineupsUseCase:
    """Recover at most ten known fixtures, with no position/score publication port."""

    def __init__(self, source: PositionAuditSnapshotSource, provider: LineupEvidenceProvider,
                 archive: LineupEvidenceArchive):
        self._source = source
        self._provider = provider
        self._archive = archive

    async def execute(
        self, *, season: str, team_external_id: int, max_fixtures: int = 10,
    ) -> RecoverMissingLineupsResult:
        await self._archive.acquire()
        try:
            return await self._execute(season=season, team_external_id=team_external_id, max_fixtures=max_fixtures)
        finally:
            await self._archive.release()

    async def _execute(
        self, *, season: str, team_external_id: int, max_fixtures: int,
    ) -> RecoverMissingLineupsResult:
        if (type(team_external_id) is not int or team_external_id <= 0
                or type(max_fixtures) is not int or not 1 <= max_fixtures <= 10):
            raise ValueError("Expected a team identity and a batch of 1..10 fixtures")
        snapshot = await self._source.load()
        data = json.loads(snapshot.content)
        if (data.get("schema") != "sfa-position-audit-snapshot-v1" or data.get("read_only") is not True
                or data.get("season") != season or data.get("acquisition")):
            raise ValueError("Expected the original read-only season snapshot, not a derived corpus")
        fixture_ids = [f["external_id"] for f in data["fixtures"]]
        if len(set(fixture_ids)) != len(fixture_ids):
            raise ValueError("Duplicate fixture inventory identity")
        cutoff = datetime.fromisoformat(data["captured_at"])
        inventory = [f for f in data["fixtures"] if f["season"] == season
                     and team_external_id in (f["home_team_external_id"], f["away_team_external_id"])
                     and f["status"] in {"FT", "AET", "PEN"} and datetime.fromisoformat(f["played_at"]) <= cutoff]
        cached = {item["payload"]["fixture"]["external_id"] for item in data["cache"]
                  if any(lineup.get("team", {}).get("external_id") == team_external_id and lineup.get("start_xi")
                         for lineup in item["payload"].get("lineups", []))}
        missing = sorted((f for f in inventory if f["external_id"] not in cached),
                         key=lambda f: (f["played_at"], f["external_id"]), reverse=True)
        selected = sorted(missing[:max_fixtures], key=lambda f: (f["played_at"], f["external_id"]))
        selected_ids = [f["external_id"] for f in selected]
        existing = await self._archive.load_manifest()
        manifest = json.loads(existing) if existing else {
            "schema": "sfa-lineup-recovery-v1", "original_sha256": snapshot.sha256,
            "season": season, "team_external_id": team_external_id, "selected_fixture_ids": selected_ids,
            "http_cap": 11, "daily_reserve": 100, "requests": [], "fixtures": {},
            "selection_reason": "latest_known_completed_fixtures_without_preserved_team_lineup",
            "missing_cause": "cache_absent_cause_unknown", "state": "planned",
        }
        if (manifest["original_sha256"] != snapshot.sha256 or manifest["selected_fixture_ids"] != selected_ids
                or manifest["season"] != season or manifest["team_external_id"] != team_external_id):
            raise ValueError("Archive belongs to a different input/selection; use another run directory")
        attempts_before = len(manifest["requests"])

        async def checkpoint() -> None:
            await self._archive.save_manifest(json.dumps(manifest, sort_keys=True, indent=2))

        async def request(fixture_id: int | None) -> LineupEvidenceResponse:
            record = {"fixture_id": fixture_id, "endpoint": "fixtures/lineups" if fixture_id else "status",
                      "state": "attempt_started"}
            manifest["requests"].append(record)
            await checkpoint()
            response = (await self._provider.fetch_lineups(fixture_id) if fixture_id is not None
                        else await self._provider.status())
            if response.fixture_id != fixture_id:
                response = replace(response, fixture_id=fixture_id, transport_error="fixture_identity_mismatch")
            digest = await self._archive.save_response(response)
            record.update({key: value for key, value in asdict(response).items() if key != "body"})
            record.update(state="captured", sha256=digest)
            record["error"] = _decode(response)[1]
            await checkpoint()
            return response

        await checkpoint()
        preserved = {}
        pending = []
        for fixture in selected:
            identity = fixture["external_id"]
            saved = await self._archive.load_response(identity)
            if saved is not None:
                preserved[identity] = saved
            else:
                pending.append(fixture)
        manifest["state"] = manifest["state"] if not pending else "running"
        quota = None
        if any(record["state"] == "attempt_started" for record in manifest["requests"]):
            manifest["state"] = "uncertain_previous_attempt"
        elif any(_normalize(preserved[f["external_id"]], f)[1] not in {"recovered", "provider_empty"}
                 for f in selected if f["external_id"] in preserved):
            manifest["state"] = "archived_error_requires_new_run"
        elif pending and len(manifest["requests"]) < manifest["http_cap"]:
            quota = await request(None)
            status, error = _decode(quota)
            if error or status.get("active") is not True:
                manifest["state"] = error or "access_unavailable"
            else:
                for fixture in pending:
                    if len(manifest["requests"]) >= manifest["http_cap"]:
                        manifest["state"] = "http_budget_exhausted"
                        break
                    if quota.daily_remaining is None or quota.minute_remaining is None or quota.minute_limit is None:
                        manifest["state"] = "quota_unknown"
                        break
                    if quota.daily_remaining <= 100 or quota.minute_remaining <= 1 or quota.minute_limit <= 0:
                        manifest["state"] = "quota_margin_exhausted"
                        break
                    quota = await request(fixture["external_id"])
                    preserved[fixture["external_id"]] = quota
                    _, error = _decode(quota)
                    if error:
                        manifest["state"] = error
                        break
                    _, outcome = _normalize(quota, fixture)
                    if outcome == "unsupported_schema":
                        manifest["state"] = outcome
                        break
                else:
                    manifest["state"] = "completed"
        elif pending:
            manifest["state"] = "http_budget_exhausted"
        recovered = []
        for fixture in selected:
            identity = fixture["external_id"]
            response = preserved.get(identity)
            if response is None:
                manifest["fixtures"][str(identity)] = "not_attempted"
                continue
            entry, outcome = _normalize(response, fixture)
            manifest["fixtures"][str(identity)] = outcome
            if entry:
                recovered.append(entry)
        manifest["acquisition"] = {
            "status_calls": sum(r["fixture_id"] is None for r in manifest["requests"]),
            "lineup_calls": sum(r["fixture_id"] is not None for r in manifest["requests"]),
            "failed_attempts": sum(r["state"] != "captured" or bool(r.get("error"))
                                   for r in manifest["requests"]),
            "original_sha256": snapshot.sha256, "state": manifest["state"],
        }
        overlay = json.loads(snapshot.content)
        replacements = {entry["payload"]["fixture"]["external_id"]: entry for entry in recovered}
        superseded = [item for item in overlay["cache"]
                      if item["payload"]["fixture"]["external_id"] in replacements
                      and _compatible_partial(item, replacements[item["payload"]["fixture"]["external_id"]])]
        overlay["cache"] = [item for item in overlay["cache"] if item not in superseded] + recovered
        overlay["previous_incomplete_cache"] = superseded
        overlay["acquisition"] = manifest["acquisition"]
        overlay["starter_denominator_available"] = False
        await self._archive.save_snapshot(json.dumps(overlay, sort_keys=True, indent=2, ensure_ascii=False))
        await checkpoint()
        result = {**manifest, "http_calls_this_execution": len(manifest["requests"]) - attempts_before,
                  "already_preserved_fixture_ids": sorted(cached.intersection(f["external_id"] for f in inventory)),
                  "not_selected_missing_fixture_ids": [f["external_id"] for f in missing[max_fixtures:]]}
        return RecoverMissingLineupsResult(json.dumps(result, sort_keys=True, indent=2))
