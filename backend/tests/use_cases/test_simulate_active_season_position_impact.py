import json
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from sfa.application.use_cases.simulate_active_season_position_impact import (
    SimulateActiveSeasonPositionImpactUseCase,
    rank_totals,
)
from sfa.domain.scoring.event_engine import EventScoringEngine
from sfa.domain.scoring.services import SFAScoringService
from sfa.domain.scoring.value_objects import ScoringConfig
from sfa.domain.scoring_ports import PlayerEventRawContextDTO

SAMPLE = Path(__file__).parents[1] / "fixtures/player_positions/impact-scoring-sample.json"


def inputs():
    sample = json.loads(SAMPLE.read_text("utf8"))
    old, raw, f = sample["score"], sample["raw"], sample["fixture"]
    pid, team = old["player_id"], sample["team_id"]
    old["position"] = "EXT"
    data = {"rules": sample["rules"], "version": 4, "raw_events": [raw], "scores": [old],
            "competitions": sample["competitions"], "fixtures": [f], "stats": [],
            "achievements": [], "bonuses": [], "honors": [],
            "rollups": [{"player_id": pid, "team_id": team, "competition_id": f["competition_id"],
                         "season": f["season"], "total_pts": old["final_points"], "achievement_bonus_pts": 0}],
            "ranking": [{"player_id": pid, "player_name": "arbitrary", "total_pts": old["final_points"], "rank": 1}]}
    catalog = [{"player_id": pid, "status": "candidate", "team_id": team, "proposed_position": "DEL",
                "accepted_references": []}]
    observations = [{"player_id": pid, "fixture_id": f["id"], "team_id": team, "starter": True,
                     "role": "CF", "side": "CENTER", "projection": "DEL", "issue": None}]
    return data, catalog, observations


def run(data, catalog, observations):
    result = SimulateActiveSeasonPositionImpactUseCase().execute(data, catalog=catalog, observations=observations)
    return json.loads(result.report_json), json.loads(result.deltas_json), json.loads(result.event_deltas_json)


def test_scoring_replay_reproduces_real_stats_before_a_position_counterfactual_without_mutation():
    data, catalog, observations = inputs()
    frozen = deepcopy(data)
    report, rows, events = run(data, catalog, observations)
    assert report["parity"]["exact_numeric"] == 1
    assert not any(v for k, v in report["parity"].items() if k not in {"exact_numeric", "stored_event_scores"})
    assert events[0]["before_position"] == "EXT" and events[0]["after_position"] == "DEL"
    assert rows[0]["delta"] == events[0]["delta"] and rows[0]["delta"] != 0
    assert data == frozen and report["production_writes"] == 0


def test_missing_or_ambiguous_slot_does_not_assign_a_majority_to_unobserved_fixtures():
    data, catalog, observations = inputs()
    for records in ([], observations + [observations[0] | {"projection": "EXT", "role": "W"}],
                    [observations[0] | {"projection": None, "role": "UNKNOWN"}]):
        report, rows, events = run(data, catalog, records)
        assert rows[0]["delta"] == 0 and events == []


def test_fixture_conflict_between_teams_cannot_escape_a_clean_recent_candidate_profile():
    data, catalog, observations = inputs()
    # The catalog can have a clean recent majority while this older fixture is
    # contradictory. Both a second XI and opposing bench membership must block it.
    for starter in (True, False):
        other = observations[0] | {"team_id": 999, "starter": starter}
        _, rows, events = run(data, catalog, observations + [other])
        assert rows[0]["delta"] == 0 and not events


def test_reference_protection_applies_to_numeric_simulation_too():
    data, catalog, observations = inputs()
    catalog[0]["accepted_references"] = [{"position": "MCO"}]
    _, rows, events = run(data, catalog, observations)
    assert rows[0]["delta"] == 0 and not events


def test_missing_temporal_elo_retains_baseline_and_reports_blocked_scope():
    data, catalog, observations = inputs()
    data["raw_events"][0]["player_team_strength"] = None
    report, rows, events = run(data, catalog, observations)
    assert report["parity"]["errors"][0]["reason"] == "missing_temporal_elo_snapshot"
    assert report["blocked_competition_seasons"] and rows[0]["delta"] == 0 and not events


def test_explanation_mismatch_blocks_the_scope_even_with_matching_final_points():
    data, catalog, observations = inputs()
    data["scores"][0]["calculation_details"] = {"changed": True}
    report, rows, events = run(data, catalog, observations)
    assert report["parity"]["calculation_details_mismatch_ids"]
    assert rows[0]["delta"] == 0 and not events


def test_ranking_baseline_mismatch_fails_instead_of_claiming_precise_movements():
    data, catalog, observations = inputs()
    data["ranking"][0]["total_pts"] += 1
    with pytest.raises(ValueError, match="Frozen ranking"):
        run(data, catalog, observations)


def test_unsupported_goalkeeper_scoring_is_not_replaced_with_an_artificial_zero():
    data, catalog, observations = inputs()
    catalog[0]["proposed_position"] = "GK"
    observations[0]["projection"] = "GK"
    _, rows, events = run(data, catalog, observations)
    assert rows[0]["delta"] == 0 and not events


def test_sql_rank_ties_zero_and_negative_values_are_preserved():
    assert rank_totals({4: Decimal("-1"), 3: Decimal("0"), 2: Decimal("5"), 1: Decimal("5")}) == [
        {"player_id": 1, "rank": 1, "points": 5}, {"player_id": 2, "rank": 1, "points": 5},
        {"player_id": 3, "rank": 3, "points": 0}, {"player_id": 4, "rank": 4, "points": -1}]


def test_reranking_the_entire_catalog_allows_a_player_outside_top50_to_enter():
    totals = {i: Decimal(100 - i) for i in range(1, 52)}
    before = rank_totals(totals)
    assert before[50]["player_id"] == 51
    after = rank_totals(totals | {51: Decimal(101)})
    assert after[0]["player_id"] == 51 and after[50]["player_id"] == 50


def test_bonus_dependency_closure_changes_a_teammate_without_reclassifying_him():
    data, _, _ = inputs()
    raw = dict(data["raw_events"][0])
    for key in ("player_birth_date", "fixture_date"):
        raw[key] = date.fromisoformat(raw[key]) if raw[key] else None
    source = PlayerEventRawContextDTO(**raw)
    config = ScoringConfig.from_dict(data["rules"][0]["config_json"])
    assert config.enable_performance_based_achievement_bonus
    service = SFAScoringService(config)
    engine = EventScoringEngine()
    comp, season, fid = source.competition_id, source.season, source.fixture_id
    team = data["rollups"][0]["team_id"]
    data["raw_events"], data["scores"], data["rollups"], data["ranking"], data["stats"] = [], [], [], [], []
    data["achievements"] = [{"id": 77, "team_id": team, "competition_id": comp, "season": season,
                             "bonus_points": 1000, "weight": 1, "phase": "winner"}]
    for pid in range(1, 5):
        event = replace(source, event_id=pid, player_id=pid, player_position="MC", event_type="goal",
                        minute=10, score_diff=0, psxg=None, player_team_strength=50.0,
                        rival_team_strength=54.0 - pid)
        score = engine._score_event(event, service, 4)
        values = asdict(event)
        for key in ("player_birth_date", "fixture_date"):
            values[key] = values[key].isoformat() if values[key] else None
        data["raw_events"].append(values)
        data["scores"].append(asdict(score))
        bonus = 1050 if pid <= 3 else 990
        data["rollups"].append({"player_id": pid, "team_id": team, "competition_id": comp, "season": season,
                                "total_pts": score.final_points, "achievement_bonus_pts": bonus})
        data["ranking"].append({"player_id": pid, "player_name": str(pid), "rank": pid,
                                "total_pts": score.final_points + bonus})
        data["stats"].append({"fixture_id": fid, "player_id": pid, "team_id": team, "minutes": 90, "rating": 6.3})
    data["bonuses"] = [{"player_id": pid, "achievement_id": 77, "final_bonus": 1050 if pid <= 3 else 990}
                       for pid in range(1, 5)]
    catalog = [{"player_id": 4, "team_id": team, "status": "candidate", "proposed_position": "DC",
                "accepted_references": []}]
    observations = [{"player_id": 4, "fixture_id": fid, "team_id": team, "starter": True,
                     "role": "CB", "side": "RIGHT", "projection": "DC", "issue": None}]
    report, rows, _ = run(data, catalog, observations)
    assert not report["parity"]["bonus_errors"] and not report["parity"]["ranking_errors"]
    teammate = next(row for row in rows if row["player_id"] == 3)
    assert teammate["event_delta"] == 0 and teammate["bonus_delta"] == -60
    assert next(row for row in rows if row["player_id"] == 4)["bonus_delta"] == 60
