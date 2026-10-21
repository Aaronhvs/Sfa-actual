import json
from copy import deepcopy
from pathlib import Path

import pytest

from sfa.application.use_cases.audit_active_season_positions import AuditActiveSeasonPositionsUseCase

CORPUS = Path(__file__).parents[1] / "fixtures/player_positions/dembele-five-starts-2026.json"


def snapshot():
    data = json.loads(CORPUS.read_text("utf8"))
    fixtures, snapshots, stats = [], [], []
    team_ids = sorted({i for v in data["versions"] for i in v["participant_team_ids"]})
    for index, v in enumerate(data["versions"], 1):
        fixtures.append({"id": index, "external_id": v["fixture_external_id"], "season": "2026", "status": "FT",
                         "competition_id": v["competition_id"], "played_at": v["played_at"],
                         "home_team_id": v["participant_team_ids"][0], "away_team_id": v["participant_team_ids"][1]})
        snapshots.append({"id": index, "fixture_id": index, "team_id": 85, "payload_hash": v["payload_sha256"],
                          "payload": {"formation": v["formation"], "start_xi": [
                              {"external_id": p["external_id"], "grid": p["grid"], "position": p["coarse_position"]}
                              for p in v["starters"]]}})
        stats.append({"player_id": 7571, "team_id": 85, "fixture_id": index, "minutes": 90})
    return {"schema": "active-season-position-impact-v1",
            "meta": {"read_only": "on", "captured_at": data["captured_at"]},
            "players": [{"id": 7571, "external_id": 153, "name": "arbitrary name", "position": "EXT"}],
            "ranking": [{"player_id": 7571, "rank": 1, "total_pts": 1000, "position": "EXT"}],
            "teams": [{"id": i, "external_id": i, "name": str(i)} for i in team_ids],
            "competitions": [{"id": i, "participant_kind": "club"} for i in (9, 10)],
            "fixtures": fixtures, "snapshots": snapshots, "stats": stats, "assignments": []}


def test_full_catalog_audit_compares_effective_position_and_club_season_without_writes():
    data = snapshot()
    before = deepcopy(data)
    result = AuditActiveSeasonPositionsUseCase().execute(data)
    row = json.loads(result.catalog_json)[0]
    assert (row["effective_position"], row["proposed_position"], row["status"]) == ("EXT", "DEL", "candidate")
    assert row["recent"]["observations"] == 5 and not row["publishable"]
    assert json.loads(result.summary_json)["candidate_transitions"] == {"EXT->DEL": 1}
    assert data == before


def test_accepted_mco_reference_is_not_downgraded_by_starting_geometry():
    data = snapshot()
    data["ranking"][0]["position"] = "MCO"
    data["assignments"] = [{"player_id": 7571, "position": "MCO", "team_id": None, "season": None,
                            "status": "accepted", "effective_from": "2026-01-01", "effective_until": None}]
    row = json.loads(AuditActiveSeasonPositionsUseCase().execute(data).catalog_json)[0]
    assert row["stored_position"] == "EXT" and row["effective_position"] == "MCO"
    assert row["observed_position"] == "DEL" and row["proposed_position"] == "MCO"
    assert row["status"] == "protected_reference_conflict"


def test_missing_evidence_remains_visible_and_enters_prioritized_recovery():
    data = snapshot()
    data["snapshots"] = []
    result = AuditActiveSeasonPositionsUseCase().execute(data)
    row = json.loads(result.catalog_json)[0]
    assert row["status"] == "insufficient_evidence" and row["proposed_position"] is None
    assert len(json.loads(result.recovery_queue_json)) == 5


def test_bench_assertion_conflicting_with_start_is_quarantined():
    data = snapshot()
    data["snapshots"][0]["payload"]["substitutes"] = [{"external_id": 153}]
    row = json.loads(AuditActiveSeasonPositionsUseCase().execute(data).catalog_json)[0]
    assert row["status"] == "ambiguous" and row["recent"]["observations"] == 4


def test_duplicate_catalog_identity_is_rejected():
    data = snapshot()
    data["players"].append(data["players"][0] | {"id": 99})
    with pytest.raises(ValueError, match="crosswalk"):
        AuditActiveSeasonPositionsUseCase().execute(data)


def test_statistical_thresholds_do_not_change_the_observed_position():
    data = snapshot()
    before = AuditActiveSeasonPositionsUseCase().execute(data).catalog_json
    for stat in data["stats"]:
        stat.update(interceptions=99, saves=9, goals=0, assists=0)
    assert AuditActiveSeasonPositionsUseCase().execute(data).catalog_json == before


def test_reaching_candidate_status_does_not_hide_missing_lineups():
    data = snapshot()
    data["snapshots"] = data["snapshots"][1:]
    result = AuditActiveSeasonPositionsUseCase().execute(data)
    assert json.loads(result.catalog_json)[0]["status"] == "candidate"
    assert json.loads(result.recovery_queue_json)[0]["fixture_id"] == 1


def test_starter_in_one_team_and_bench_in_opponent_is_a_fixture_conflict():
    data = snapshot()
    f = data["fixtures"][0]
    opponent = next(t for t in (f["home_team_id"], f["away_team_id"]) if t != 85)
    data["snapshots"].append({"id": 999, "fixture_id": f["id"], "team_id": opponent, "payload_hash": "retained",
                              "payload": {"formation": "4-3-3", "start_xi": [],
                                          "substitutes": [{"external_id": 153}]}})
    row = json.loads(AuditActiveSeasonPositionsUseCase().execute(data).catalog_json)[0]
    assert row["status"] == "ambiguous" and row["recent"]["observations"] == 4


def test_world_cup_or_national_appearance_cannot_override_current_club_context():
    data = snapshot()
    data["competitions"].append({"id": 350, "participant_kind": "national"})
    data["fixtures"].append(data["fixtures"][0] | {
        "id": 99, "external_id": 999, "competition_id": 350, "played_at": "2026-10-18T12:00:00+00:00"})
    data["stats"].append({"player_id": 7571, "team_id": 85, "fixture_id": 99, "minutes": 90})
    result = AuditActiveSeasonPositionsUseCase().execute(data)
    row = json.loads(result.catalog_json)[0]
    assert row["recent"]["competition_ids"] == [9, 10] and row["proposed_position"] == "DEL"
    assert row["appearances"] == 5 and not json.loads(result.recovery_queue_json)


def test_two_appearances_use_only_original_family_and_never_enter_recovery():
    data = snapshot()
    data["stats"] = data["stats"][:2]
    data["snapshots"] = data["snapshots"][:1]
    result = AuditActiveSeasonPositionsUseCase().execute(data)
    row = json.loads(result.catalog_json)[0]
    assert row["proposed_position"] == "DEL"
    assert row["assertion_kind"] == "provider_family" and row["verification_status"] == "unverified"
    assert not json.loads(result.recovery_queue_json)
    data["snapshots"] = []
    row = json.loads(AuditActiveSeasonPositionsUseCase().execute(data).catalog_json)[0]
    assert row["proposed_position"] is None and row["family_assertion_kind"] == "legacy_unverified"


def test_latest_direct_revision_removes_historical_conflict_without_mutating_original():
    data = snapshot()
    original = data["snapshots"][0]
    contradiction = deepcopy(original)
    contradiction["id"] = "bad-cache"
    contradiction["payload_hash"] = "bad"
    contradiction["payload"]["substitutes"] = [{"external_id": 153}]
    data["snapshots"].append(contradiction)
    before = deepcopy(data)
    assert json.loads(AuditActiveSeasonPositionsUseCase().execute(data).catalog_json)[0]["status"] == "ambiguous"
    direct = original | {"id": "direct-refresh", "authority": "api-football-direct-validated",
                         "fetched_at": "2026-10-20T00:00:00+00:00"}
    result = AuditActiveSeasonPositionsUseCase().execute(data, supplementary=(direct,))
    assert json.loads(result.catalog_json)[0]["proposed_position"] == "DEL"
    assert json.loads(result.catalog_json)[0]["status"] == "candidate"
    assert len(json.loads(result.summary_json)["provider_supersessions"]) == 1
    assert data == before
