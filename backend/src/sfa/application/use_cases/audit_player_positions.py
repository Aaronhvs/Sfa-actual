from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sfa.domain.player_position_overrides import position_for_context
from sfa.domain.player_positions.longitudinal import PlayerPositionTimeline
from sfa.domain.player_positions.ports import PositionAuditSnapshotSource
from sfa.domain.player_positions.services import LineupPositionInterpreter, aggregate_position_support
from sfa.domain.player_positions.value_objects import (
    LineupSlot,
    PlayerStartEvidence,
    PositionProfileContext,
    StartingLineup,
)


@dataclass(frozen=True)
class PlayerPositionAuditResult:
    report_json: str


def _starting_assertions(payload: dict) -> str:
    """Ignore presentation/enrichment fields when comparing cached start evidence."""
    summary = payload.get("fixture", {})
    rows = []
    for lineup in payload.get("lineups", []):
        players = [(p.get("external_id"), p.get("grid"), p.get("position")) for p in lineup.get("start_xi", [])]
        rows.append((lineup.get("team", {}).get("external_id"), lineup.get("formation"), sorted(players, key=repr)))
    return json.dumps({"fixture": summary.get("external_id"),
                       "home": summary.get("home_team", {}).get("external_id"),
                       "away": summary.get("away_team", {}).get("external_id"), "lineups": sorted(rows, key=repr)},
                      sort_keys=True)


class AuditPlayerPositionsUseCase:
    """Replay captured lineups without providers, persistence or score recalculation."""

    def __init__(self, source: PositionAuditSnapshotSource):
        self._source = source

    async def execute(self, *, as_of: str | None = None) -> PlayerPositionAuditResult:
        snapshot = await self._source.load()
        data = json.loads(snapshot.content)
        if data.get("schema") != "sfa-position-audit-snapshot-v1" or data.get("read_only") is not True:
            raise ValueError("Unsupported read-only snapshot contract")
        season = data["season"]
        players = data["players"]
        if len({p["id"] for p in players}) != len(players):
            raise ValueError("Duplicate internal catalog identities")
        external_ids = [p["external_id"] for p in players if p["external_id"] is not None]
        if len(set(external_ids)) != len(external_ids):
            raise ValueError("Ambiguous catalog crosswalk")
        crosswalk = {p["external_id"]: p for p in players if p["external_id"] is not None}
        scoped_fixtures = [f for f in data["fixtures"] if f["season"] == season]
        if len({f["external_id"] for f in scoped_fixtures}) != len(scoped_fixtures):
            raise ValueError("Duplicate fixture inventory identity")
        fixtures = {f["external_id"]: f for f in scoped_fixtures}
        profile_as_of = as_of or data["captured_at"]
        cutoff = datetime.fromisoformat(profile_as_of)
        if cutoff.tzinfo is None:
            raise ValueError("Profile cutoff must include a timezone")
        profile_as_of = cutoff.astimezone(timezone.utc).isoformat()
        interpreter = LineupPositionInterpreter()
        observations = []
        exclusions = Counter()
        contexts = defaultdict(list)
        evidence_players = set()
        cached_fixtures = set()
        lineup_results = []
        start_contexts = defaultdict(list)
        effective_by_context = defaultdict(set)
        appearances = []

        def record_starts(raw: dict, fixture: dict, interpreted=None, issue: str | None = None,
                          source_ref: str | None = None) -> None:
            team_id = raw.get("team", {}).get("external_id")
            if team_id not in (fixture["home_team_external_id"], fixture["away_team_external_id"]):
                return
            ids = Counter(p.get("external_id") for p in raw.get("start_xi", []))
            observed = {o.external_id: o for o in interpreted.observations} if interpreted else {}
            for player in raw.get("start_xi", []):
                identity = player.get("external_id")
                if type(identity) is not int or identity <= 0 or ids[identity] != 1 or identity not in crosswalk:
                    continue
                context = PositionProfileContext(identity, team_id, season, fixture["competition_id"])
                baseline = crosswalk[identity]
                effective = position_for_context(
                    baseline["position"], player_name=baseline["name"],
                    team_name=raw.get("team", {}).get("name"), competition_id=fixture["competition_id"],
                )
                if effective:
                    effective_by_context[context].add(effective)
                start_contexts[context].append(PlayerStartEvidence(
                    context, fixture["external_id"], fixture["played_at"], observed.get(identity), issue, source_ref,
                ))
            for field, status in (("start_xi", "starter"), ("substitutes", "substitute")):
                for player in raw.get(field, []):
                    identity = player.get("external_id")
                    if identity in crosswalk:
                        appearances.append({"player_id": crosswalk[identity]["id"], "external_id": identity,
                                            "fixture_id": fixture["external_id"], "team_id": team_id,
                                            "status": status, "grid": player.get("grid"),
                                            "raw_position": player.get("position"), "source_ref": source_ref})
        cache_by_key = defaultdict(list)
        for cached in data["cache"]:
            cache_by_key[cached.get("key")].append(cached)
        unique_cache = []
        for key, versions in sorted(cache_by_key.items(), key=lambda item: str(item[0])):
            payloads = {_starting_assertions(v["payload"]) for v in versions}
            if len(payloads) > 1:
                exclusions["contradictory_cache_key"] += 1
                for version in versions:
                    fixture = fixtures.get(version["payload"].get("fixture", {}).get("external_id"))
                    if fixture and version.get("key") == f"fixture:api:supplement:v2:{fixture['external_id']}":
                        for raw in version["payload"].get("lineups", []):
                            record_starts(raw, fixture, issue="contradictory_evidence", source_ref=version["key"])
            else:
                unique_cache.append(min(versions, key=lambda version: json.dumps(version, sort_keys=True)))
        for cached in unique_cache:
            payload = cached["payload"]
            external_id = payload.get("fixture", {}).get("external_id")
            fixture = fixtures.get(external_id)
            if fixture is None:
                exclusions["cache_outside_fixture_inventory"] += 1
                continue
            if cached.get("key") != f"fixture:api:supplement:v2:{external_id}":
                exclusions["cache_key_identity_mismatch"] += 1
                continue
            cached_fixtures.add(external_id)
            participants = (fixture["home_team_external_id"], fixture["away_team_external_id"])
            cached_summary = payload.get("fixture", {})
            if (cached_summary.get("home_team", {}).get("external_id"),
                    cached_summary.get("away_team", {}).get("external_id")) != participants:
                exclusions["fixture_participant_mismatch"] += 1
                continue
            team_counts = Counter(lineup.get("team", {}).get("external_id") for lineup in payload.get("lineups", []))
            player_teams = defaultdict(set)
            for raw in payload.get("lineups", []):
                for player in raw.get("start_xi", []):
                    identity = player.get("external_id")
                    if identity is not None:
                        player_teams[identity].add(raw.get("team", {}).get("external_id"))
            if any(len(teams) > 1 for teams in player_teams.values()):
                exclusions["player_in_both_starting_teams"] += 1
                continue
            for raw in payload.get("lineups", []):
                team_id = raw.get("team", {}).get("external_id")
                if team_counts[team_id] != 1:
                    exclusions["duplicate_team_lineup"] += 1
                    record_starts(raw, fixture, issue="contradictory_evidence", source_ref=cached["key"])
                    continue
                lineup = StartingLineup(
                    fixture_id=external_id, team_id=team_id, season=season,
                    competition_id=fixture["competition_id"], played_at=fixture["played_at"],
                    formation=raw.get("formation"), participant_team_ids=participants,
                    starters=tuple(LineupSlot(p.get("external_id"), p.get("grid"), p.get("position"))
                                   for p in raw.get("start_xi", [])),
                )
                interpreted = interpreter.interpret(lineup)
                digest = cached.get("sha256") or hashlib.sha256(
                    json.dumps(payload, sort_keys=True).encode()
                ).hexdigest()
                record_starts(raw, fixture, interpreted, interpreted.reason, f"{cached['key']}@{digest}")
                lineup_results.append({"fixture_id": external_id, "team_id": team_id,
                                       "formation": lineup.formation, "reason": interpreted.reason,
                                       "observations": len(interpreted.observations)})
                if interpreted.reason:
                    exclusions[interpreted.reason] += 1
                for observation in interpreted.observations:
                    player = crosswalk.get(observation.external_id)
                    item = asdict(observation)
                    item["candidates"] = sorted(role.value for role in observation.candidates)
                    item["player_id"] = player["id"] if player else None
                    item["name"] = player["name"] if player else None
                    item["stored_position"] = player["position"] if player else None
                    item["legacy_effective_position"] = position_for_context(
                        player["position"], player_name=player["name"], team_name=raw.get("team", {}).get("name"),
                        competition_id=fixture["competition_id"],
                    ) if player else None
                    item["differs_from_legacy_effective"] = (
                        observation.sfa_position is not None and player is not None
                        and observation.sfa_position != item["legacy_effective_position"]
                    )
                    observations.append(item)
                    if player:
                        evidence_players.add(player["id"])
                        contexts[(player["id"], team_id, fixture["competition_id"])].append(observation)
                    else:
                        exclusions["unmapped_player_identity"] += 1
        summaries = defaultdict(list)
        for (player_id, team_id, competition_id), values in sorted(contexts.items()):
            support = asdict(aggregate_position_support(tuple(values)))
            support.update({"team_id": team_id, "competition_id": competition_id, "season": season,
                            "period_start": min(v.played_at for v in values),
                            "period_end": max(v.played_at for v in values)})
            summaries[player_id].append(support)
        longitudinal = defaultdict(list)
        for context, starts in sorted(start_contexts.items(), key=lambda item: (
                item[0].external_id, item[0].team_id, item[0].competition_id)):
            timeline = PlayerPositionTimeline(context)
            for start in starts:
                timeline = timeline.update(start)
            preview = asdict(timeline.preview(as_of=profile_as_of))
            effective = sorted(effective_by_context[context])
            primary = preview["recent"]["primary_position"]
            preview["legacy_effective_positions"] = effective
            preview["candidate_comparison"] = (
                "insufficient_candidate" if primary is None else "mixed_legacy_context" if len(effective) != 1
                else "matches_legacy" if primary == effective[0] else "differs_from_legacy"
            )
            longitudinal[crosswalk[context.external_id]["id"]].append(preview)
        catalog = [{**player, "status": "candidate_only" if player["id"] in evidence_players
                    else "uninterpretable_cached_starts" if player["id"] in longitudinal else "no_cached_evidence",
                    "next_action": "collect_more_lineups_and_starter_inventory" if player["id"] in evidence_players
                    else "validate_lineup_evidence" if player["id"] in longitudinal
                    else "collect_lineup_evidence", "contexts": summaries[player["id"]],
                    "longitudinal": longitudinal[player["id"]]} for player in players]
        report = {
            "schema": "sfa-position-audit-report-v1",
            "mode": "offline-enriched-candidate-simulation" if data.get("acquisition")
            else "cache-only-candidate-simulation",
            "acquisition": data.get("acquisition"),
            "snapshot_sha256": snapshot.sha256, "captured_at": data["captured_at"], "season": season,
            "profile_as_of": profile_as_of, "longitudinal_policy_version": "longitudinal-profile-v1",
            "rules_fingerprint": data.get("rules_fingerprint"), "production_writes": 0, "provider_calls": 0,
            "scope_note": "Physical fixture season; not an award-scope or historical correction simulation.",
            "policy": {"min_fixtures": 3, "min_support": "2/3", "min_start_coverage": "60%",
                       "coverage_denominator": "unavailable: player_stats does not identify starting appearances",
                       "templates": "starting-grid-v1", "orientation": "column-1-team-left-v1",
                       "projection": "sfa-projection-v1", "semantic_accuracy_measured": False},
            "summary": {
                "catalog_players": len(players), "players_with_cached_evidence": len(evidence_players),
                "players_without_cached_evidence": len(players) - len(evidence_players),
                "season_fixtures": len(fixtures), "cached_season_fixtures": len(cached_fixtures),
                "fixtures_without_cache": len(fixtures) - len(cached_fixtures),
                "valid_team_lineups": sum(item["reason"] is None for item in lineup_results),
                "invalid_team_lineups": sum(item["reason"] is not None for item in lineup_results),
                "slot_observations": len(observations),
                "projection_discrepancy_observations": sum(o["differs_from_legacy_effective"] for o in observations),
                "eligible_contexts": sum(c["eligible"] for values in summaries.values() for c in values),
                "longitudinal_contexts": sum(len(items) for items in longitudinal.values()),
                "longitudinal_recent_primary": sum(p["recent"]["primary_position"] is not None
                                                   for items in longitudinal.values() for p in items),
                "longitudinal_change_proposals": sum(change["state"] == "change_proposed"
                                                     for items in longitudinal.values() for p in items
                                                     for change in p["proposals"]),
                "longitudinal_different_candidates": sum(p["candidate_comparison"] == "differs_from_legacy"
                                                        for items in longitudinal.values() for p in items),
                "exclusions": dict(sorted(exclusions.items())),
            },
            "lineups": lineup_results, "observations": sorted(
                observations, key=lambda o: (o["fixture_id"], o["team_id"], o["external_id"])
            ), "catalog": catalog,
            "appearance_evidence": sorted(appearances, key=lambda item: (
                item["fixture_id"], item["team_id"], item["external_id"], item["status"], item["source_ref"] or "")),
        }
        return PlayerPositionAuditResult(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
