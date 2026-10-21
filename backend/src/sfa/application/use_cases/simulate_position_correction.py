from __future__ import annotations

import json
from dataclasses import asdict, replace
from decimal import ROUND_HALF_UP, Decimal

from sfa.domain.player_positions.ports import PositionCorrectionRepository
from sfa.domain.player_positions.publication import (
    PositionCorrectionPlan,
    PositionCorrectionRequest,
    canonical,
    digest,
)
from sfa.domain.scoring.event_engine import EventScoringEngine, _build_b1_contributions_map
from sfa.domain.scoring.services import SFAScoringService
from sfa.domain.scoring_ports import PlayerEventScoreRepositoryPort, ScoringRulesVersionRepositoryPort

_NUMERIC_FIELDS = ("base_points", "m1", "m2", "m3", "m4", "mvisit", "mrating",
                   "combined_before_clamp", "combined_after_clamp", "final_points")


class SimulatePositionCorrectionUseCase:
    def __init__(self, corrections: PositionCorrectionRepository, events: PlayerEventScoreRepositoryPort,
                 rules: ScoringRulesVersionRepositoryPort):
        self._corrections, self._events, self._rules = corrections, events, rules

    async def execute(self, request: PositionCorrectionRequest, rules_version_id: int) -> PositionCorrectionPlan:
        rules = await self._rules.get_version_by_id(rules_version_id)
        if rules is None or not rules.is_active:
            raise ValueError("Curated publication requires the active immutable rules version")
        capture = await self._corrections.capture(request, rules_version_id)
        source = json.loads(capture.source_json)
        raw = await self._events.get_events_for_recalc(request.season, None, None, request.player_id)
        stored = json.loads(capture.scores_json)
        retained = {row["event_id"]: row for row in stored}
        if {e.event_id for e in raw} != set(retained):
            raise ValueError("Raw/stored event sets differ; establish complete scoring before publication")
        names = await self._events.get_competition_name_map()
        contributions = _build_b1_contributions_map(raw)
        scorer, service = EventScoringEngine(), SFAScoringService(rules.config)
        changes, deltas, observed_fixtures = [], {}, set()
        for event in raw:
            before = retained[event.event_id]
            baseline = scorer._score_event(replace(event, player_position=before["position"]), service,
                                           rules_version_id, names, contributions)
            if baseline is None or any(Decimal(str(before[k])) != Decimal(str(getattr(baseline, k)))
                                       for k in _NUMERIC_FIELDS):
                raise ValueError(f"Stored scoring parity failed for event {event.event_id}")
            if event.fixture_id not in request.fixture_ids:
                continue
            observed_fixtures.add(event.fixture_id)
            after_score = scorer._score_event(replace(event, player_position=request.position), service,
                                              rules_version_id, names, contributions)
            if after_score is None:
                raise ValueError(f"Corrected event {event.event_id} cannot be scored")
            after = dict(before)
            after.update({k: str(getattr(after_score, k)) for k in _NUMERIC_FIELDS})
            after.update(position=request.position, calculation_details=after_score.calculation_details)
            after["calculation_details"]["position_decision"] = {
                "decision_id": digest(request.manifest_data), "source_ref": request.source_ref,
                "assertion_kind": ("habitual_football_role" if request.schema_version == 1
                                   else "curated_fixture_scoring_role"),
                "policy": f"curated-fixture-evidence-v{request.schema_version}",
                "accepted_at": request.accepted_at, "applicable_fixture_ids": list(request.fixture_ids),
                "evidence_ids": sorted(e["id"] for e in source.get("evidence", [])),
                "basis": ("curated_user_confirmation_and_retained_starting_evidence" if request.schema_version == 1
                          else "reviewed_scoring_decision_with_retained_starting_evidence"), "fixture_id": event.fixture_id,
            }
            changes.append({"before": before, "after": after})
            key = event.competition_id
            deltas[key] = deltas.get(key, Decimal(0)) + Decimal(str(after_score.final_points)) - Decimal(
                str(before["final_points"]))
        if observed_fixtures != set(request.fixture_ids):
            raise ValueError("Every allowed fixture requires complete scored events")
        # Bonuses whose inputs are raw statistics remain invariant. Rank-based team
        # achievement bonuses require a wider publisher; this bounded release fails closed.
        if source["rank_dependent_achievements"]:
            raise ValueError("Achievement rank dependency requires an expanded correction batch")
        rollups = []
        replacements = {c["after"]["event_id"]: c["after"] for c in changes}
        for before in json.loads(capture.rollups_json):
            comp = before["competition_id"]
            if comp not in deltas:
                continue
            rows = [replacements.get(r["event_id"], r) for r in stored if r["competition_id"] == comp]
            # Verify the persisted rollup baseline, including every noncorrected appearance.
            old_rows = [r for r in stored if r["competition_id"] == comp]
            if Decimal(str(before["total_pts"])) != sum(Decimal(str(r["final_points"])) for r in old_rows):
                raise ValueError("Persisted season aggregate differs from its scored events")
            after = dict(before)
            total = sum(Decimal(str(r["final_points"])) for r in rows)
            after["total_pts"] = str(total)
            breakdown = {}
            for row in rows:
                entry = breakdown.setdefault(row["action_type"], {"count": 0, "pts": Decimal(0)})
                entry["count"] += 1
                entry["pts"] += Decimal(str(row["final_points"]))
            for entry in breakdown.values():
                points = entry["pts"]
                entry["pct"] = float((points / total * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) \
                    if total else 0.0
                entry["pts"] = float(points)
            after["breakdown"] = breakdown
            rollups.append({"before": before, "after": after})
        if {c["before"]["competition_id"] for c in rollups} != set(deltas):
            raise ValueError("Missing affected season rollup")
        dependencies = {"source": source, "raw": [asdict(e) for e in raw], "rules": asdict(rules), "names": names,
                        "scores": stored, "rollups": json.loads(capture.rollups_json)}
        # Dates/enums/sets in immutable domain DTOs use a stable JSON representation.
        encoded = json.dumps(dependencies, default=lambda v: sorted(v) if isinstance(v, (set, frozenset)) else str(v),
                             sort_keys=True)
        report = {"fixtures": list(request.fixture_ids), "events": len(changes), "rollups": len(rollups),
                  "deltas_by_competition": {str(k): str(v) for k, v in deltas.items()},
                  "total_delta": str(sum(deltas.values())), "baseline_events_verified": len(raw),
                  "honors": "raw-statistics inputs unchanged", "automatic_acceptance": False}
        return PositionCorrectionPlan(
            request=request, rules_version_id=rules_version_id, input_hash=digest(json.loads(encoded)),
            engine_hash=capture.engine_hash, event_changes_json=canonical(changes),
            rollup_changes_json=canonical(rollups), dependencies_json=encoded, report_json=canonical(report),
        )
