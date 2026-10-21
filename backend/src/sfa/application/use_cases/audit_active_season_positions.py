"""Offline catalog audit. No persistence or acquisition dependency is available."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass

from sfa.domain.player_positions.club_season_audit import audit_club_season
from sfa.domain.player_positions.evidence_policy import retained_provider_versions, provider_family
from sfa.domain.player_positions.longitudinal import PlayerPositionTimeline
from sfa.domain.player_positions.services import LineupPositionInterpreter
from sfa.domain.player_positions.value_objects import (
    LineupSlot,
    PlayerStartEvidence,
    PositionProfileContext,
    StartingLineup,
)


@dataclass(frozen=True)
class ActiveSeasonPositionAuditResult:
    catalog_json: str
    observations_json: str
    recovery_queue_json: str
    summary_json: str


def _players(payload: dict, starter: bool) -> list[dict]:
    source = payload.get("startXI", payload.get("start_xi", [])) if starter else payload.get("substitutes", [])
    return [item.get("player", item) for item in source]


def _identity(player: dict) -> int | None:
    return player.get("id", player.get("external_id"))


class AuditActiveSeasonPositionsUseCase:
    def execute(self, snapshot: dict, *, supplementary: tuple[dict, ...] = ()) -> ActiveSeasonPositionAuditResult:
        if snapshot.get("schema") != "active-season-position-impact-v1" or snapshot["meta"]["read_only"] != "on":
            raise ValueError("Require a frozen read-only active season capture")
        players = {p["id"]: p for p in snapshot["players"]}
        external = {p["external_id"]: p["id"] for p in players.values() if p["external_id"] is not None}
        if len(external) != sum(p["external_id"] is not None for p in players.values()):
            raise ValueError("Ambiguous player crosswalk")
        teams = {t["id"]: t for t in snapshot["teams"]}
        fixtures = {f["id"]: f for f in snapshot["fixtures"]}
        competitions = {c["id"]: c for c in snapshot["competitions"]}
        as_of = snapshot["meta"]["captured_at"]
        scored_positions = defaultdict(Counter)
        for score in snapshot.get("scores", []):
            scored_positions[score["player_id"]][score["position"]] += 1
        accepted = defaultdict(list)
        for a in snapshot["assignments"]:
            if (a["status"] == "accepted" and a["effective_from"] <= as_of
                    and (not a["effective_until"] or a["effective_until"] > as_of)):
                accepted[a["player_id"]].append(a)
        appearances = defaultdict(list)
        for stat in snapshot["stats"]:
            f = fixtures[stat["fixture_id"]]
            if (stat["player_id"] in players and (stat["minutes"] or 0) > 0
                    and stat["team_id"] in {f["home_team_id"], f["away_team_id"]}
                    and f["status"] in {"FT", "AET", "PEN"} and f["played_at"] <= as_of
                    and competitions[f["competition_id"]]["participant_kind"] == "club"):
                appearances[stat["player_id"]].append((f, stat))
        records = []
        evidence = defaultdict(list)
        membership = defaultdict(lambda: {"start": set(), "bench": set()})
        fixture_teams = defaultdict(set)
        preserved_teams = defaultdict(set)
        interpreter = LineupPositionInterpreter()
        all_snapshots, supersessions = retained_provider_versions(snapshot, supplementary)
        for s in all_snapshots:
            if s["fixture_id"] not in fixtures or s["team_id"] not in teams:
                continue
            f, payload = fixtures[s["fixture_id"]], s["payload"]
            if competitions[f["competition_id"]]["participant_kind"] != "club":
                continue
            team = teams[s["team_id"]]["external_id"]
            participants = _players(payload, True)
            if participants:
                preserved_teams[f["id"]].add(s["team_id"])
            context_base = (team, f["season"], f["competition_id"], "club")
            lineup = StartingLineup(
                f["external_id"], team, f["season"], f["competition_id"], f["played_at"], payload.get("formation"),
                tuple(LineupSlot(_identity(p), p.get("grid"), p.get("pos", p.get("position"))) for p in participants),
                (teams[f["home_team_id"]]["external_id"], teams[f["away_team_id"]]["external_id"]),
            )
            result = interpreter.interpret(lineup)
            observed = {o.external_id: o for o in result.observations}
            for starter in (True, False):
                values = _players(payload, starter)
                counts = Counter(_identity(p) for p in values)
                for p in values:
                    identity = _identity(p)
                    if identity not in external:
                        continue
                    player_id = external[identity]
                    context = PositionProfileContext(identity, *context_base)
                    key = player_id, context, f["external_id"]
                    membership[key]["start" if starter else "bench"].add(str(s["id"]))
                    o = observed.get(identity) if starter else None
                    records.append({"player_id": player_id, "fixture_id": f["id"],
                                    "fixture_external_id": f["external_id"], "played_at": f["played_at"],
                                    "team_id": s["team_id"], "competition_id": f["competition_id"],
                                    "season": f["season"], "snapshot_id": s["id"], "starter": starter,
                                    "formation": payload.get("formation"), "grid": p.get("grid"),
                                    "source_position": p.get("pos", p.get("position")),
                                    "role": o.role.value if o else None, "side": o.side.value if o else None,
                                    "role_candidates": sorted(r.value for r in o.candidates) if o else [],
                                    "projection": o.sfa_position if o else None, "issue": result.reason})
                    fixture_teams[player_id, f["external_id"]].add(team)
                    if starter:
                        evidence[player_id, context].append(PlayerStartEvidence(
                            context, f["external_id"], f["played_at"], o if counts[identity] == 1 else None,
                            result.reason if counts[identity] == 1 else "duplicate_player_identity",
                            f"snapshot:{s['id']}@{s['payload_hash']}",
                        ))
        safe_evidence = defaultdict(list)
        for (pid, context), entries in evidence.items():
            for e in entries:
                m = membership[pid, context, e.fixture_id]
                if (m["start"] and m["bench"]) or len(fixture_teams[pid, e.fixture_id]) > 1:
                    e = PlayerStartEvidence(context, e.fixture_id, e.played_at, issue="contradictory_evidence",
                                            source_ref=e.source_ref)
                safe_evidence[pid, context].append(e)
        contexts_by_player = defaultdict(list)
        for (pid, context), values in safe_evidence.items():
            contexts_by_player[pid].append((context, values))
        records_by_player = defaultdict(list)
        for record in records:
            records_by_player[record["player_id"]].append(record)
        rows, queue = [], []
        for rank in snapshot["ranking"]:
            pid = rank["player_id"]
            p = players[pid]
            apps = sorted(appearances[pid], key=lambda a: (a[0]["played_at"], a[0]["id"]))
            current_team = apps[-1][1]["team_id"] if apps else None
            current_season = apps[-1][0]["season"] if apps else None
            current_apps = [(f, s) for f, s in apps if s["team_id"] == current_team and f["season"] == current_season]
            entries, per_competition = [], []
            for context, values in contexts_by_player[pid]:
                if (current_team is not None and context.team_id == teams[current_team]["external_id"]
                        and context.season == current_season):
                    entries.extend(values)
                    profile = PlayerPositionTimeline(context, tuple(values)).preview(as_of=as_of).recent
                    per_competition.append(asdict(profile))
            recent = asdict(audit_club_season(tuple(entries), as_of=as_of)) if entries else None
            season = asdict(audit_club_season(tuple(entries), as_of=as_of, window="season")) if entries else None
            primary = recent["primary_position"] if recent else None
            conflicts = recent["conflicting_fixture_ids"] if recent else []
            references = [a for a in accepted[pid] if (a["team_id"] is None or a["team_id"] == current_team)
                          and (a["season"] is None or a["season"] == current_season)]
            ref_positions = {a["position"] for a in references}
            protected = bool(references and (len(ref_positions) != 1 or primary not in ref_positions))
            status = ("protected_reference_conflict" if protected else "ambiguous" if conflicts else
                      "insufficient_evidence" if not recent or recent["observations"] < 3 else
                      "ambiguous" if not primary else "unchanged" if primary == rank["position"] else "candidate")
            proposal = next(iter(ref_positions)) if len(ref_positions) == 1 else primary
            missing = sorted({f["id"] for f, _ in current_apps if current_team not in preserved_teams[f["id"]]},
                             key=lambda fid: (fixtures[fid]["played_at"], fid), reverse=True)
            row = {"player_id": pid, "external_id": p["external_id"], "name": p["name"],
                   "rank": rank["rank"], "points": rank["total_pts"], "stored_position": p["position"],
                   "effective_position": rank["position"], "observed_position": primary,
                   "proposed_position": proposal, "status": status,
                   "team_id": current_team, "team_name": teams[current_team]["name"] if current_team else None,
                   "season": current_season, "recent": recent, "season_profile": season,
                   "by_competition": per_competition, "accepted_references": references,
                   "scored_position_distribution": dict(sorted(scored_positions[pid].items())),
                   "appearances": len({f["id"] for f, _ in current_apps}), "missing_appearance_fixture_ids": missing,
                   "publishable": False, "assertion_kind": "observed_starting_slot_candidate"}
            rows.append(row)
            raw = [r for r in records_by_player[pid] if r["team_id"] == current_team
                   and r["season"] == current_season and provider_family(r["source_position"])]
            latest_date = max((r["played_at"] for r in raw), default=None)
            families = {provider_family(r["source_position"]) for r in raw if r["played_at"] == latest_date}
            row["provider_family_projection"] = next(iter(families)) if len(families) == 1 else None
            row["family_assertion_kind"] = "provider_family" if raw else "legacy_unverified"
            row["verification_status"] = "unverified"
            row["acquisition_eligible"] = row["appearances"] >= 3
            if row["appearances"] < 3 and not references:
                row["status"] = "insufficient_evidence"
                row["proposed_position"] = row["provider_family_projection"]
                row["assertion_kind"] = row["family_assertion_kind"]
            # A modal role does not certify coverage. Missing XI remain pending
            # even after a player reaches the minimum evidence threshold.
            if missing and row["acquisition_eligible"]:
                for fid in missing:
                    queue.append({"player_id": pid, "name": p["name"], "points": rank["total_pts"],
                                  "baseline_rank": rank["rank"], "fixture_id": fid,
                                  "fixture_external_id": fixtures[fid]["external_id"], "team_id": current_team})
        rows.sort(key=lambda r: (-r["points"], r["player_id"]))
        queue.sort(key=lambda r: (-r["points"], r["player_id"], -r["fixture_id"]))
        unique_queue, seen = [], set()
        for item in queue:
            if item["fixture_id"] not in seen:
                unique_queue.append(item)
                seen.add(item["fixture_id"])
        summary = {"players": len(rows), "status_counts": dict(Counter(r["status"] for r in rows)),
                   "observed_transitions": dict(Counter(r["effective_position"] + "->" + r["observed_position"]
                                                        for r in rows if r["observed_position"])),
                   "candidate_transitions": dict(Counter(r["effective_position"] + "->" + r["proposed_position"]
                                                         for r in rows if r["status"] == "candidate")),
                   "pending_unique_fixtures": len(unique_queue), "publishable": 0,
                   "provider_supersessions": supersessions}
        return ActiveSeasonPositionAuditResult(*(json.dumps(value, ensure_ascii=False, default=str)
                                                  for value in (rows, records, unique_queue, summary)))
