import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from sfa.application.use_cases.audit_player_positions import AuditPlayerPositionsUseCase
from sfa.domain.player_positions.ports import PositionAuditSnapshotSource
from sfa.domain.player_positions.value_objects import PositionAuditSnapshot


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeSnapshotSource(PositionAuditSnapshotSource):
    def __init__(self, data):
        content = json.dumps(data)
        self.snapshot = PositionAuditSnapshot(content, hashlib.sha256(content.encode()).hexdigest())
        self.calls = 0

    async def load(self):
        self.calls += 1
        return self.snapshot


@pytest.fixture
def retained_snapshot():
    return json.loads((Path(__file__).parents[1] / "fixtures" / "player-position-lineups-2026.json").read_text("utf-8"))


@pytest.mark.anyio
async def test_replays_real_full_lineups_without_changing_source_or_current_positions(retained_snapshot):
    before = deepcopy(retained_snapshot)
    source = FakeSnapshotSource(retained_snapshot)
    assert isinstance(source, PositionAuditSnapshotSource)
    result = json.loads((await AuditPlayerPositionsUseCase(source).execute()).report_json)
    assert source.calls == 1 and retained_snapshot == before
    assert result["summary"]["valid_team_lineups"] == 5
    assert result["summary"]["slot_observations"] == 55
    assert result["summary"]["eligible_contexts"] == 0
    assert result["production_writes"] == result["provider_calls"] == 0
    assert len(result["catalog"]) == len(before["players"])
    camello = [o for o in result["observations"] if o["player_id"] == 75]
    assert len(camello) == 2 and all(o["role"] == "CF" and o["sfa_position"] == "DEL" for o in camello)
    fermin = next(o for o in result["observations"] if o["player_id"] == 52)
    assert fermin["sfa_position"] == fermin["legacy_effective_position"] == "MCO"
    assert not fermin["differs_from_legacy_effective"]
    ratiu = [o for o in result["observations"] if o["external_id"] == 1703]
    pedrosa = [o for o in result["observations"] if o["external_id"] == 47329]
    assert all(o["side"] == "RIGHT" and o["sfa_position"] == "LAT" for o in ratiu)
    assert all(o["side"] == "LEFT" and o["sfa_position"] == "LAT" for o in pedrosa)


@pytest.mark.anyio
async def test_classification_is_independent_of_names_legacy_positions_and_internal_enrichment(retained_snapshot):
    source = FakeSnapshotSource(retained_snapshot)
    first = json.loads((await AuditPlayerPositionsUseCase(source).execute()).report_json)
    for player in retained_snapshot["players"]:
        player.update(name="Same arbitrary name", position="MC")
    for cached in retained_snapshot["cache"]:
        for lineup in cached["payload"]["lineups"]:
            for player in lineup["start_xi"]:
                player.update(name="Unknown", player_id=None, sfa_points=9999999)
    outcome = await AuditPlayerPositionsUseCase(FakeSnapshotSource(retained_snapshot)).execute()
    second = json.loads(outcome.report_json)
    fields = ("external_id", "fixture_id", "role", "side", "candidates", "sfa_position")
    assert [[o[k] for k in fields] for o in first["observations"]] == [
        [o[k] for k in fields] for o in second["observations"]]


@pytest.mark.anyio
async def test_empty_cache_still_accounts_for_entire_catalog(retained_snapshot):
    retained_snapshot["cache"] = []
    outcome = await AuditPlayerPositionsUseCase(FakeSnapshotSource(retained_snapshot)).execute()
    result = json.loads(outcome.report_json)
    assert result["summary"]["players_without_cached_evidence"] == len(retained_snapshot["players"])
    assert all(p["status"] == "no_cached_evidence" and p["contexts"] == [] for p in result["catalog"])


@pytest.mark.anyio
@pytest.mark.parametrize("mutation,reason", [
    ("schema", "snapshot contract"), ("duplicate_internal", "internal catalog"),
    ("duplicate_external", "catalog crosswalk"),
])
async def test_invalid_snapshot_contract_or_crosswalk_is_rejected(retained_snapshot, mutation, reason):
    if mutation == "schema":
        retained_snapshot["schema"] = "other"
    elif mutation == "duplicate_internal":
        retained_snapshot["players"].append(retained_snapshot["players"][0])
    else:
        retained_snapshot["players"][1]["external_id"] = retained_snapshot["players"][0]["external_id"]
    with pytest.raises(ValueError, match=reason):
        await AuditPlayerPositionsUseCase(FakeSnapshotSource(retained_snapshot)).execute()


@pytest.mark.anyio
@pytest.mark.parametrize("mutation,reason", [
    ("outside", "cache_outside_fixture_inventory"), ("key", "cache_key_identity_mismatch"),
    ("participant", "fixture_participant_mismatch"), ("duplicate_team", "duplicate_team_lineup"),
    ("unmapped", "unmapped_player_identity"),
])
async def test_incompatible_cached_records_are_reported_without_fallback(retained_snapshot, mutation, reason):
    cached = retained_snapshot["cache"][0]
    if mutation == "outside":
        cached["payload"]["fixture"]["external_id"] = -1
    elif mutation == "key":
        cached["key"] = "wrong"
    elif mutation == "participant":
        cached["payload"]["fixture"]["home_team"]["external_id"] = -1
    elif mutation == "duplicate_team":
        cached["payload"]["lineups"].append(cached["payload"]["lineups"][0])
    else:
        retained_snapshot["players"] = []
    outcome = await AuditPlayerPositionsUseCase(FakeSnapshotSource(retained_snapshot)).execute()
    result = json.loads(outcome.report_json)
    assert result["summary"]["exclusions"][reason] > 0


@pytest.mark.anyio
async def test_duplicate_cache_payloads_are_no_op_and_conflicts_are_excluded(retained_snapshot):
    first = json.loads((await AuditPlayerPositionsUseCase(FakeSnapshotSource(retained_snapshot)).execute()).report_json)
    retained_snapshot["cache"].append(deepcopy(retained_snapshot["cache"][0]))
    outcome = await AuditPlayerPositionsUseCase(FakeSnapshotSource(retained_snapshot)).execute()
    second = json.loads(outcome.report_json)
    assert first["summary"] == second["summary"] and first["observations"] == second["observations"]
    retained_snapshot["cache"][-1]["payload"]["lineups"][0]["formation"] = "4-4-2"
    third = json.loads((await AuditPlayerPositionsUseCase(FakeSnapshotSource(retained_snapshot)).execute()).report_json)
    assert third["summary"]["exclusions"]["contradictory_cache_key"] == 1
    assert third["summary"]["slot_observations"] == first["summary"]["slot_observations"] - 22


@pytest.mark.anyio
async def test_duplicate_fixture_identity_is_not_silently_overwritten(retained_snapshot):
    retained_snapshot["fixtures"].append(retained_snapshot["fixtures"][0])
    with pytest.raises(ValueError, match="fixture inventory"):
        await AuditPlayerPositionsUseCase(FakeSnapshotSource(retained_snapshot)).execute()


@pytest.mark.anyio
async def test_player_cannot_start_for_both_teams(retained_snapshot):
    teams = retained_snapshot["cache"][0]["payload"]["lineups"]
    teams[1]["start_xi"][0]["external_id"] = teams[0]["start_xi"][0]["external_id"]
    outcome = await AuditPlayerPositionsUseCase(FakeSnapshotSource(retained_snapshot)).execute()
    result = json.loads(outcome.report_json)
    assert result["summary"]["exclusions"]["player_in_both_starting_teams"] == 1


@pytest.mark.anyio
async def test_longitudinal_preview_preserves_unknown_coverage_and_invalid_known_starts(retained_snapshot):
    source = FakeSnapshotSource(retained_snapshot)
    report = json.loads((await AuditPlayerPositionsUseCase(source).execute()).report_json)
    assert source.calls == 1 and report["provider_calls"] == report["production_writes"] == 0
    assert report["longitudinal_policy_version"] == "longitudinal-profile-v1"
    profiles = [profile for player in report["catalog"] for profile in player["longitudinal"]]
    assert any(profile["recent"]["excluded_starts"] > 0 for profile in profiles)
    assert all(profile["recent"]["start_coverage"] is None for profile in profiles)
    assert all(profile["recent"]["candidate_only"] for profile in profiles)
    assert all(profile["recent"]["profile_kind"] == "observed_starting_slots" for profile in profiles)
    assert all(not profile["recent"]["meets_evidence_gates"] for profile in profiles)
    assert any(player["status"] == "uninterpretable_cached_starts" for player in report["catalog"])


@pytest.mark.anyio
async def test_substitute_never_inherits_a_starting_role_or_adds_a_start(retained_snapshot):
    raw = retained_snapshot["cache"][0]["payload"]["lineups"][0]
    raw["substitutes"] = [{"external_id": 340626, "name": "Unrelated label", "position": "M", "grid": None}]
    outcome = await AuditPlayerPositionsUseCase(FakeSnapshotSource(retained_snapshot)).execute()
    report = json.loads(outcome.report_json)
    player = next(p for p in report["catalog"] if p["id"] == 52)
    assert len(player["longitudinal"]) == 1
    assert player["longitudinal"][0]["season"]["selected_starts"] == 1
    assert player["longitudinal"][0]["season"]["context"]["team_id"] == 529
    bench = [a for a in report["appearance_evidence"] if a["external_id"] == 340626 and a["status"] == "substitute"]
    assert len(bench) == 1 and bench[0]["grid"] is None and "role" not in bench[0]


@pytest.mark.anyio
async def test_cutoff_prevents_future_observations_affecting_profiles(retained_snapshot):
    report = json.loads((await AuditPlayerPositionsUseCase(FakeSnapshotSource(retained_snapshot)).execute(
        as_of="2026-01-01T00:00:00+00:00")).report_json)
    assert all(profile["season"]["observations"] == 0 for player in report["catalog"]
               for profile in player["longitudinal"])


@pytest.mark.anyio
async def test_naive_profile_cutoff_is_rejected_even_with_empty_cache(retained_snapshot):
    retained_snapshot["cache"] = []
    with pytest.raises(ValueError, match="timezone"):
        await AuditPlayerPositionsUseCase(FakeSnapshotSource(retained_snapshot)).execute(as_of="2026-10-18")


@pytest.mark.anyio
async def test_metadata_only_cache_versions_do_not_quarantine_real_starting_evidence(retained_snapshot):
    duplicate = deepcopy(retained_snapshot["cache"][0])
    duplicate["payload"]["lineups"].reverse()
    for lineup in duplicate["payload"]["lineups"]:
        lineup["start_xi"].reverse()
        for player in lineup["start_xi"]:
            player.update(name="New display name", sfa_points=99999, player_id=None)
    retained_snapshot["cache"].append(duplicate)
    outcome = await AuditPlayerPositionsUseCase(FakeSnapshotSource(retained_snapshot)).execute()
    report = json.loads(outcome.report_json)
    assert report["summary"]["slot_observations"] == 55
    assert "contradictory_cache_key" not in report["summary"]["exclusions"]
    assert all(profile["season"]["conflicting_fixture_ids"] == [] for player in report["catalog"]
               for profile in player["longitudinal"])


@pytest.mark.anyio
async def test_conflicting_cache_versions_remain_known_but_excluded_from_profile_support(retained_snapshot):
    duplicate = deepcopy(retained_snapshot["cache"][0])
    duplicate["payload"]["lineups"][0]["formation"] = "4-4-2"
    retained_snapshot["cache"].append(duplicate)
    outcome = await AuditPlayerPositionsUseCase(FakeSnapshotSource(retained_snapshot)).execute()
    report = json.loads(outcome.report_json)
    assert report["summary"]["exclusions"]["contradictory_cache_key"] == 1
    assert any(profile["season"]["conflicting_fixture_ids"] for player in report["catalog"]
               for profile in player["longitudinal"])
