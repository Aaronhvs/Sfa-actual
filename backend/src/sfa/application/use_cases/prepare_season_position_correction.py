"""Compile one reviewed season batch, with a closed numerical dependency graph."""
from __future__ import annotations

import json
from collections import defaultdict
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol

from sfa.domain.player_positions.ports import SeasonPositionImpactSimulator
from sfa.domain.player_positions.publication import SeasonPositionCorrectionPlan, canonical, digest
from sfa.domain.scoring.event_engine import EventScoringEngine, _build_b1_contributions_map
from sfa.domain.scoring.services import SFAScoringService
from sfa.domain.scoring.value_objects import ScoringConfig
from sfa.domain.scoring_ports import PlayerEventRawContextDTO

POLICY = "reviewed-season-six-valid-75pct-v2"
NUMERIC = ("base_points", "m1", "m2", "m3", "m4", "mvisit", "mrating",
           "combined_before_clamp", "combined_after_clamp", "final_points")


def pilot_eligible(row: dict) -> bool:
    recent, season = row.get("recent") or {}, row.get("season_profile") or {}
    observations = recent.get("observations", 0)
    support = next((v["count"] for v in recent.get("position_distribution", ())
                    if v["value"] == row.get("proposed_position")), 0)
    return (row["status"] == "candidate" and row["proposed_position"] in {"DC", "LAT", "MC", "MCO", "EXT", "DEL"}
            and row["appearances"] >= 3 and observations >= 6 and support * 4 >= observations * 3
            and season.get("primary_position") == row["proposed_position"]
            and not recent.get("conflicting_fixture_ids") and not row.get("accepted_references"))


def _breakdown(rows):
    result = {}
    total = sum(Decimal(str(r["final_points"])) for r in rows)
    for row in rows:
        item = result.setdefault(row["action_type"], {"count": 0, "pts": Decimal(0)})
        item["count"] += 1
        item["pts"] += Decimal(str(row["final_points"]))
    for item in result.values():
        item["pct"] = float((item["pts"] / total * 100).quantize(Decimal(".1"), rounding=ROUND_HALF_UP)) if total else 0.0
        item["pts"] = float(item["pts"])
    return result


class PrepareSeasonPositionCorrectionUseCaseProtocol(Protocol):
    async def execute(self, snapshot: dict, *, catalog: list[dict], observations: list[dict],
                      evidence: list[dict], source_hash: str, engine_hash: str,
                      accepted_at: str, actor: str) -> SeasonPositionCorrectionPlan: ...


class PrepareSeasonPositionCorrectionUseCase(PrepareSeasonPositionCorrectionUseCaseProtocol):
    def __init__(self, impact: SeasonPositionImpactSimulator):
        self._impact = impact

    async def execute(self, snapshot: dict, *, catalog: list[dict], observations: list[dict],
                evidence: list[dict], source_hash: str, engine_hash: str,
                accepted_at: str, actor: str) -> SeasonPositionCorrectionPlan:
        scope = snapshot["scope"]
        if scope["key"] != "season-2026" or scope.get("includes_world_cup") or not actor.strip():
            raise ValueError("This pilot is restricted to the approved club award period")
        pairs = {(s["season"], c) for s in scope["sources"] for c in s["competition_ids"]}
        if any(s != "2026" or c == 350 for s, c in pairs):
            raise ValueError("Other seasons and World Cup are outside this pilot")
        if datetime.fromisoformat(accepted_at).tzinfo is None:
            raise ValueError("Acceptance requires a real timezone-aware instant")
        selected = {r["player_id"]: r for r in catalog if pilot_eligible(r)}
        if not selected:
            raise ValueError("No reviewed candidates meet this pilot's evidence policy")
        reduced = [r if r["player_id"] in selected else dict(r, status="not_selected_for_pilot") for r in catalog]
        outcome = self._impact.execute(snapshot, catalog=reduced, observations=observations)
        report = json.loads(outcome.report_json)
        if report["blocked_competition_seasons"] or any(report["parity"][key] for key in (
                "errors", "calculation_details_mismatch_ids", "rollup_errors", "bonus_errors",
                "bonus_rollup_errors", "ranking_errors")):
            raise ValueError("Complete baseline/dependency parity is required before publication")
        fixtures = {f["id"]: f for f in snapshot["fixtures"]}
        players = {p["id"]: p for p in snapshot["players"]}
        teams = {t["id"]: t for t in snapshot["teams"]}
        assertions, benches, memberships = defaultdict(set), set(), defaultdict(set)
        for o in observations:
            key = o["player_id"], o["fixture_id"], o["team_id"]
            memberships[o["player_id"], o["fixture_id"]].add(o["team_id"])
            if o["starter"]:
                assertions[key].add((o["projection"], o["role"], o["side"], o["issue"]))
            else:
                benches.add(key)
        stored = {s["event_id"]: s for s in snapshot["scores"]}
        scored_fixtures = {(s["player_id"], s["fixture_id"]) for s in stored.values()}
        decisions, classifications = [], []
        allowed = {}
        for pid, row in selected.items():
            target, team = row["proposed_position"], row["team_id"]
            accepted = []
            for (p, fid, t), values in assertions.items():
                if p != pid or t != team or len(values) != 1 or (p, fid, t) in benches or len(memberships[p, fid]) != 1:
                    continue
                projection, role, side, issue = next(iter(values))
                f = fixtures[fid]
                if (projection != target or issue or (f["season"], f["competition_id"]) not in pairs
                        or (p, fid) not in scored_fixtures):
                    continue
                if datetime.fromisoformat(f["played_at"]) >= datetime.fromisoformat(accepted_at):
                    raise ValueError("A correction cannot predate the evidence it accepts")
                allowed[p, fid] = target
                accepted.append(fid)
            if not accepted:
                raise ValueError(f"Selected player {pid} has no complete scored fixture with compatible evidence")
            proof = {"player_id": pid, "external_player_id": players[pid]["external_id"],
                     "team_id": team, "external_team_id": teams[team]["external_id"], "season": row["season"],
                     "position": target, "fixture_ids": sorted(accepted), "accepted_at": accepted_at,
                     "source_ref": "user-delegated:season-2026-position-pilot", "actor": actor,
                     "assertion_kind": "curated_fixture_scoring_role", "policy": POLICY,
                     "basis": "reviewed_scoring_classification_from_retained_starting_evidence",
                     "statement": "Curated SFA scoring category; starting slots do not establish habitual role or minutes",
                     "recent_observations": row["recent"]["observations"],
                     "position_distribution": row["recent"]["position_distribution"], "coverage": "unknown"}
            proof["decision_id"] = digest(proof)
            decisions.append(proof)
            # Aggregate season view is explicitly approved. Filtered competition
            # views require that competition's own profile to agree with it.
            authorized = sorted({p["context"]["competition_id"] for p in row["by_competition"]
                                 if p["primary_position"] == target and p["observations"] >= 3})
            classifications.append({"player_id": pid, "team_id": team, "scope_key": scope["key"],
                                    "position": target, "competition_ids": authorized,
                                    "scope_competition_ids": sorted(c for _, c in pairs),
                                    "assertion_kind": "scope_scoring_classification",
                                    "decision_id": proof["decision_id"], "coverage": "unknown", "policy": POLICY})
        decision_map = {d["player_id"]: d for d in decisions}
        raw = []
        for values in snapshot["raw_events"]:
            values = dict(values)
            for key in ("player_birth_date", "fixture_date"):
                if values[key]:
                    values[key] = date.fromisoformat(values[key])
            raw.append(PlayerEventRawContextDTO(**values))
        raw_map = {r.event_id: r for r in raw}
        config = ScoringConfig.from_dict(snapshot["rules"][0]["config_json"])
        engine, scorer = EventScoringEngine(), SFAScoringService(config)
        contributions = _build_b1_contributions_map(raw)
        names = {c["id"]: c["name"] for c in snapshot["competitions"]}
        changes = []
        for old in stored.values():
            key = old["player_id"], old["fixture_id"]
            if key not in allowed:
                continue
            after_score = engine._score_event(replace(raw_map[old["event_id"]], player_position=allowed[key]),
                                              scorer, snapshot["version"], names, contributions)
            if after_score is None:
                raise ValueError("Every approved event must remain scoreable")
            after = deepcopy(old)
            after.update({k: getattr(after_score, k) for k in NUMERIC})
            after.update(position=allowed[key], calculation_details=deepcopy(after_score.calculation_details))
            decision = decision_map[key[0]]
            after["calculation_details"]["position_decision"] = {
                "decision_id": decision["decision_id"], "assertion_kind": decision["assertion_kind"],
                "source_ref": decision["source_ref"], "policy": POLICY, "accepted_at": accepted_at,
                "fixture_id": key[1], "coverage": "unknown", "scope_key": scope["key"]}
            changes.append({"before": old, "after": after})
        bonus_before = {(b["player_id"], b["achievement_id"]): b for b in snapshot["bonuses"]}
        details_before = {(b["player_id"], b["achievement_id"]): b for b in report["bonus_details_before"]}
        bonus_changes = []
        for detail in report["bonus_details_after"]:
            key = detail["player_id"], detail["achievement_id"]
            if detail["calculation_details"] == details_before[key]["calculation_details"]:
                continue
            old = bonus_before[key]
            after = dict(old, final_bonus=detail["bonus"], calculation_details=detail["calculation_details"])
            bonus_changes.append({"before": old, "after": after})
        replacements = {c["after"]["event_id"]: c["after"] for c in changes}
        affected = {(c["before"]["player_id"], c["before"]["competition_id"], c["before"]["season"]) for c in changes}
        affected.update((c["before"]["player_id"], c["before"]["competition_id"], c["before"]["season"])
                        for c in bonus_changes)
        bonus_replacements = {c["after"]["id"]: c["after"] for c in bonus_changes}
        rollups = []
        for old in snapshot["rollups"]:
            key = old["player_id"], old["competition_id"], old["season"]
            if key not in affected:
                continue
            rows = [replacements.get(s["event_id"], s) for s in stored.values()
                    if (s["player_id"], s["competition_id"], s["season"]) == key]
            bonuses = [bonus_replacements.get(b["id"], b) for b in snapshot["bonuses"]
                       if (b["player_id"], b["competition_id"], b["season"]) == key]
            after = dict(old, total_pts=float(sum(Decimal(str(r["final_points"])) for r in rows)),
                         achievement_bonus_pts=float(sum(Decimal(str(b["final_bonus"])) for b in bonuses)),
                         breakdown=_breakdown(rows))
            rollups.append({"before": old, "after": after})
        report.update(schema_version=2, selected_classifications=len(classifications),
                      journal_events=len(changes), journal_rollups=len(rollups), journal_bonuses=len(bonus_changes),
                      policy=POLICY, actual_habitual_references_inserted=0, published=False)
        return SeasonPositionCorrectionPlan(canonical(scope), snapshot["version"], accepted_at, actor,
                                            source_hash, engine_hash, canonical(decisions), canonical(classifications),
                                            canonical(changes), canonical(rollups), canonical(bonus_changes),
                                            canonical(evidence), canonical(report))
