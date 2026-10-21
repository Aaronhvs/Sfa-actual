"""Frozen, in-memory counterfactual. No database, publisher or provider ports."""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from sfa.application.use_cases.calculate_achievement_bonuses import (
    _compute_effective_participation,
    _compute_performance_factor,
    _compute_rank_factor,
    _compute_rating_factor,
)
from sfa.domain.scoring.event_engine import EventScoringEngine, _build_b1_contributions_map
from sfa.domain.scoring.services import SFAScoringService
from sfa.domain.scoring.value_objects import ScoringConfig
from sfa.domain.scoring_ports import PlayerEventRawContextDTO


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def rank_totals(totals: dict[int, Decimal]) -> list[dict]:
    """SQL rank() semantics plus deterministic player-ID ordering, including <=0."""
    rows, previous, rank = [], None, 0
    for index, (pid, total) in enumerate(sorted(totals.items(), key=lambda item: (-item[1], item[0])), 1):
        if total != previous:
            rank = index
        rows.append({"player_id": pid, "rank": rank, "points": float(total)})
        previous = total
    return rows


@dataclass(frozen=True)
class ActiveSeasonPositionImpactResult:
    report_json: str
    deltas_json: str
    event_deltas_json: str
    rankings_json: str


class SimulateActiveSeasonPositionImpactUseCase:
    def execute(self, snapshot: dict, *, catalog: list[dict],
                observations: list[dict]) -> ActiveSeasonPositionImpactResult:
        config = ScoringConfig.from_dict(snapshot["rules"][0]["config_json"])
        service, engine = SFAScoringService(config), EventScoringEngine()
        raws = []
        for row in snapshot["raw_events"]:
            values = dict(row)
            for key in ("player_birth_date", "fixture_date"):
                if values[key]:
                    values[key] = date.fromisoformat(values[key])
            raws.append(PlayerEventRawContextDTO(**values))
        raw_by_id = {r.event_id: r for r in raws}
        stored = {s["event_id"]: s for s in snapshot["scores"]}
        names = {c["id"]: c["name"] for c in snapshot["competitions"]}
        b1 = _build_b1_contributions_map(raws)
        fields = ("base_points", "m1", "m2", "m3", "m4", "mvisit", "mrating",
                  "combined_before_clamp", "combined_after_clamp", "final_points")
        parity_errors, baseline, detail_mismatches = [], {}, []
        for event_id, old in stored.items():
            raw = raw_by_id.get(event_id)
            if raw is None:
                parity_errors.append({"event_id": event_id, "reason": "missing_raw_context"})
                continue
            if any(value is None for value in (raw.player_team_strength, raw.rival_team_strength,
                                                raw.player_team_elo_raw, raw.rival_team_elo_raw,
                                                raw.elo_model_version)):
                parity_errors.append({"event_id": event_id, "reason": "missing_temporal_elo_snapshot"})
                continue
            before = engine._score_event(replace(raw, player_position=old["position"]), service,
                                         snapshot["version"], names, b1)
            mismatch = {key: {"stored": old[key], "replay": getattr(before, key) if before else None}
                        for key in fields if before is None
                        or Decimal(str(old[key])) != Decimal(str(getattr(before, key)))}
            if mismatch:
                parity_errors.append({"event_id": event_id, "differences": mismatch})
            else:
                baseline[event_id] = before
                if before.calculation_details != old["calculation_details"]:
                    detail_mismatches.append(event_id)
        rolls = {(r["player_id"], r["competition_id"], r["season"]): r for r in snapshot["rollups"]}
        event_totals = defaultdict(Decimal)
        for s in stored.values():
            event_totals[s["player_id"], s["competition_id"], s["season"]] += _money(s["final_points"])
        rollup_errors = [{"key": key, "stored": r["total_pts"], "event_sum": str(event_totals[key])}
                         for key, r in rolls.items() if _money(r["total_pts"]) != event_totals[key]]
        fixtures = {f["id"]: f for f in snapshot["fixtures"]}
        stats_by_scope, team_fixtures, team_players = defaultdict(list), defaultdict(set), defaultdict(set)
        for stat in snapshot["stats"]:
            f = fixtures[stat["fixture_id"]]
            stats_by_scope[stat["player_id"], f["competition_id"], f["season"]].append(stat)
            key = stat["team_id"], f["competition_id"], f["season"]
            team_fixtures[key].add(f["id"])
            if (stat["minutes"] or 0) > 0:
                team_players[key].add(stat["player_id"])

        def achievement_bonuses(totals):
            ranks, grouped = {}, defaultdict(dict)
            for key, r in rolls.items():
                grouped[r["team_id"], r["competition_id"], r["season"]][r["player_id"]] = totals[key]
            for key, values in grouped.items():
                for row in rank_totals(values):
                    ranks[key, row["player_id"]] = row["rank"]
            result, details = {}, []
            for a in snapshot["achievements"]:
                team_key = a["team_id"], a["competition_id"], a["season"]
                minutes = len(team_fixtures[team_key]) * 90
                if not minutes:
                    continue
                for pid in sorted(team_players[team_key]):
                    raw_stats = stats_by_scope[pid, a["competition_id"], a["season"]]
                    player_minutes = sum(s["minutes"] or 0 for s in raw_stats)
                    ratio = min(1.0, player_minutes / minutes)
                    participation = _compute_effective_participation(ratio)
                    rank = ranks.get((team_key, pid), 12)
                    ratings = [s["rating"] for s in raw_stats if s["rating"] is not None]
                    average = float(sum(Decimal(str(r)) for r in ratings) / len(ratings)) if ratings else None
                    factor = (_compute_performance_factor(_compute_rank_factor(rank, ratio),
                                                           _compute_rating_factor(average))
                              if config.enable_performance_based_achievement_bonus else 1.0)
                    bonus = round(a["bonus_points"] * float(a["weight"]) * participation * factor, 2)
                    result[pid, a["id"]] = _money(bonus)
                    calculation = {"phase": a["phase"], "bonus_points": a["bonus_points"],
                                   "competition_weight": float(a["weight"]), "player_minutes": player_minutes,
                                   "team_total_minutes": minutes, "participation_ratio": round(ratio, 4),
                                   "effective_participation": round(participation, 4), "rank_in_team": rank,
                                   "rank_factor": _compute_rank_factor(rank, ratio), "avg_rating": average,
                                   "rating_factor": _compute_rating_factor(average),
                                   "performance_factor": round(factor, 4), "final_bonus": bonus}
                    details.append({"player_id": pid, "achievement_id": a["id"], "rank_in_team": rank,
                                    "bonus": bonus, "competition_id": a["competition_id"], "season": a["season"],
                                    "calculation_details": calculation})
            return result, details

        old_totals = {key: _money(r["total_pts"]) for key, r in rolls.items()}
        bonuses_before, bonus_details_before = achievement_bonuses(old_totals)
        saved_bonuses = {(b["player_id"], b["achievement_id"]): _money(b["final_bonus"]) for b in snapshot["bonuses"]}
        bonus_errors = [{"key": key, "stored": str(saved_bonuses.get(key)), "replay": str(bonuses_before.get(key))}
                        for key in sorted(set(saved_bonuses) | set(bonuses_before))
                        if saved_bonuses.get(key) != bonuses_before.get(key)]
        achievement_map = {a["id"]: a for a in snapshot["achievements"]}
        bonus_rollups = defaultdict(Decimal)
        for (pid, aid), value in saved_bonuses.items():
            a = achievement_map[aid]
            bonus_rollups[pid, a["competition_id"], a["season"]] += value
        bonus_rollup_errors = [{"key": key, "stored": r["achievement_bonus_pts"], "bonus_sum": str(bonus_rollups[key])}
                               for key, r in rolls.items() if _money(r["achievement_bonus_pts"]) != bonus_rollups[key]]
        full_totals = defaultdict(Decimal)
        for key, r in rolls.items():
            full_totals[key[0]] += _money(r["total_pts"]) + _money(r["achievement_bonus_pts"])
        for h in snapshot["honors"]:
            full_totals[h["player_id"]] += _money(h["awarded_bonus_pts"])
        public = {r["player_id"]: r for r in snapshot["ranking"]}
        ranking_errors = [{"player_id": pid, "stored": r["total_pts"], "rollup_total": str(full_totals[pid])}
                          for pid, r in public.items() if _money(r["total_pts"]) != full_totals[pid]]
        baseline_ranks = {r["player_id"]: r for r in rank_totals({pid: full_totals[pid] for pid in public})}
        ranking_errors.extend({"player_id": pid, "reason": "rank_mismatch"}
                              for pid, r in public.items() if r["rank"] != baseline_ranks[pid]["rank"])
        if ranking_errors:
            raise ValueError("Frozen ranking totals/ranks do not reproduce; resolve baseline before impact simulation")
        slots, benches, participant_teams = defaultdict(set), set(), defaultdict(set)
        for o in observations:
            key = o["player_id"], o["fixture_id"], o["team_id"]
            participant_teams[o["player_id"], o["fixture_id"]].add(o["team_id"])
            if o["starter"]:
                slots[key].add((o["role"], o["side"], o["projection"], o["issue"]))
            else:
                benches.add(key)
        candidates = {r["player_id"]: r for r in catalog if r["status"] == "candidate"}
        eligible = {}
        for (pid, fid, team), assertions in slots.items():
            r = candidates.get(pid)
            if (r and r["team_id"] == team and len(assertions) == 1 and (pid, fid, team) not in benches
                    and len(participant_teams[pid, fid]) == 1
                    and not r["accepted_references"]):
                role, side, projection, issue = next(iter(assertions))
                if projection == r["proposed_position"] and not issue:
                    eligible[pid, fid] = projection
        # Component failures retain the whole affected competition-season scope.
        detail_mismatch_ids = set(detail_mismatches)
        blocked_scopes = {(s["competition_id"], s["season"]) for s in stored.values()
                          if s["event_id"] not in baseline or s["event_id"] in detail_mismatch_ids}
        blocked_scopes.update((e["key"][1], e["key"][2]) for e in rollup_errors + bonus_rollup_errors)
        for e in bonus_errors:
            a = achievement_map[e["key"][1]]
            blocked_scopes.add((a["competition_id"], a["season"]))
        deltas, event_deltas, excluded = defaultdict(Decimal), [], []
        changed_totals = dict(old_totals)
        by_fixture = defaultdict(list)
        for s in stored.values():
            by_fixture[s["player_id"], s["fixture_id"]].append(s)
        for key, proposal in eligible.items():
            scores = by_fixture[key]
            if not scores or all(s["position"] == proposal for s in scores):
                continue
            f = fixtures[key[1]]
            if (f["competition_id"], f["season"]) in blocked_scopes:
                excluded.append({"player_id": key[0], "fixture_id": key[1],
                                 "reason": "dependency_or_parity_unresolved"})
                continue
            if proposal == "GK":
                excluded.append({"player_id": key[0], "fixture_id": key[1], "reason": "unsupported_scoring_position"})
                continue
            changes = []
            for old in scores:
                after = engine._score_event(replace(raw_by_id[old["event_id"]], player_position=proposal),
                                            service, snapshot["version"], names, b1)
                if after is None:
                    changes = []
                    excluded.append({"player_id": key[0], "fixture_id": key[1],
                                     "reason": "unsupported_scoring_position"})
                    break
                changes.append((old, after))
            for old, after in changes:
                delta = _money(after.final_points) - _money(old["final_points"])
                roll_key = old["player_id"], old["competition_id"], old["season"]
                changed_totals[roll_key] += delta
                deltas[old["player_id"]] += delta
                event_deltas.append({"event_id": old["event_id"], "player_id": old["player_id"],
                                     "fixture_id": old["fixture_id"], "competition_id": old["competition_id"],
                                     "before_position": old["position"], "after_position": proposal,
                                     "before": old["final_points"], "after": after.final_points, "delta": float(delta),
                                     "before_base": old["base_points"], "after_base": after.base_points,
                                     "action": old["action_type"]})
        bonuses_after, bonus_details_after = achievement_bonuses(changed_totals)
        bonus_deltas = defaultdict(Decimal)
        bonus_changes = []
        for key, value in bonuses_after.items():
            a = achievement_map[key[1]]
            if (a["competition_id"], a["season"]) in blocked_scopes:
                continue
            delta = value - bonuses_before[key]
            if delta:
                bonus_deltas[key[0]] += delta
                bonus_changes.append({"player_id": key[0], "achievement_id": key[1],
                                      "before": float(bonuses_before[key]),
                                      "after": float(value), "delta": float(delta)})
        before_totals = {pid: full_totals[pid] for pid in public}
        after_totals = {pid: total + deltas[pid] + bonus_deltas[pid] for pid, total in before_totals.items()}
        before_ranking, after_ranking = rank_totals(before_totals), rank_totals(after_totals)
        before_map, after_map = ({r["player_id"]: r for r in rows} for rows in (before_ranking, after_ranking))
        player_deltas = [{"player_id": pid, "name": public[pid]["player_name"],
                          "before_rank": before_map[pid]["rank"], "after_rank": after_map[pid]["rank"],
                          "rank_gain": before_map[pid]["rank"] - after_map[pid]["rank"],
                          "before_points": float(before_totals[pid]), "after_points": float(after_totals[pid]),
                          "event_delta": float(deltas[pid]), "bonus_delta": float(bonus_deltas[pid]),
                          "delta": float(after_totals[pid] - before_totals[pid])}
                         for pid in before_totals]
        player_deltas.sort(key=lambda r: (r["before_rank"], r["player_id"]))
        top_before, top_after = ({r["player_id"] for r in rows[:50]} for rows in (before_ranking, after_ranking))
        report = {"hypothesis": "fixture_backed_starting_slot", "production_writes": 0,
                  "parity": {"stored_event_scores": len(stored), "exact_numeric": len(baseline),
                             "errors": parity_errors, "calculation_details_mismatch_ids": detail_mismatches,
                             "rollup_errors": rollup_errors, "bonus_errors": bonus_errors,
                             "bonus_rollup_errors": bonus_rollup_errors, "ranking_errors": ranking_errors},
                  "blocked_competition_seasons": sorted(blocked_scopes), "excluded": excluded,
                  "changed_events": sum(r["delta"] != 0 for r in event_deltas),
                  "changed_fixtures": len({(r["player_id"], r["fixture_id"]) for r in event_deltas}),
                  "changed_players": sum(r["delta"] != 0 for r in player_deltas),
                  "bonus_changes": bonus_changes, "bonus_rows_replayed": len(bonuses_before),
                  "bonus_details_before": bonus_details_before, "bonus_details_after": bonus_details_after,
                  "honors_invariant": ("Raw goals/assists/dribbles/duels/minutes unchanged; "
                                       "no position input; frozen honor rows retained"),
                  "top50_entries": sorted(top_after - top_before), "top50_exits": sorted(top_before - top_after),
                  "after_nonpositive_players": [pid for pid, points in after_totals.items() if points <= 0],
                  "top50_rank_changes": sum(r["before_rank"] != r["after_rank"] for r in player_deltas
                                            if r["player_id"] in top_before | top_after)}
        return ActiveSeasonPositionImpactResult(*(json.dumps(value, ensure_ascii=False, default=str) for value in (
            report, player_deltas, event_deltas, {"before": before_ranking, "after": after_ranking})))
