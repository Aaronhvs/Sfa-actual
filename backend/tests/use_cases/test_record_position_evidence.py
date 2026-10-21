from __future__ import annotations

import json
from pathlib import Path

import pytest

from sfa.application.use_cases.record_position_evidence import RecordPositionEvidenceUseCase
from sfa.domain.player_positions.ports import (
    PlayerPositionEvidenceRepository,
    PositionFixtureContext,
    RecordPositionEvidenceResult,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeEvidenceRepository:
    def __init__(self):
        self.context = PositionFixtureContext(1, 100, 1, "2026", "2026-10-18T12:00:00+00:00", ((529, 1), (530, 2)))
        self.captures = ()
        self.coverage = None
        self.players = {}
        self.writes = 0

    async def get_fixture_context(self, external_id):
        return self.context

    async def get_player_ids(self, external_ids):
        return {external: external + 1000 for external in external_ids if external not in self.players}

    async def record_lineups(self, context, captures, source_ref, received_at, coverage_json):
        self.writes += 1
        self.captures = captures
        self.coverage = json.loads(coverage_json)
        return RecordPositionEvidenceResult(context.external_id, len(captures), sum(len(c.evidence) for c in captures),
                                            "recorded")


def lineup(team=529, offset=0, formation="4-3-3"):
    positions = [(1, 1, "G"), *[(2, col, "D") for col in range(1, 5)],
                 *[(3, col, "M") for col in range(1, 4)], *[(4, col, "F") for col in range(1, 4)]]
    return {"team": {"id": team}, "formation": formation,
            "startXI": [{"player": {"id": offset + n, "name": f"Arbitrary {n}", "pos": pos, "grid": f"{row}:{col}"}}
                        for n, (row, col, pos) in enumerate(positions, 1)],
            "substitutes": [{"player": {"id": offset + 12, "pos": "M", "grid": None}}]}


async def capture(repo, lineups):
    return await RecordPositionEvidenceUseCase(repo).execute(
        100, json.dumps({"response": lineups}), "test:raw-response", "2026-10-18T12:00:00+00:00",
    )


@pytest.mark.anyio
async def test_durable_capture_keeps_starting_slots_separate_from_habitual_roles():
    repo = FakeEvidenceRepository()
    assert isinstance(repo, PlayerPositionEvidenceRepository)
    result = await capture(repo, [lineup(), lineup(530, 20)])
    assert result.snapshots == 2
    assert result.evidence == 24
    assert repo.coverage["both_starting_elevens"] is True
    assert repo.coverage["calendar_reconciled"] is False
    assert repo.coverage["status"] == "partial"
    first = repo.captures[0]
    assert first.validation_status == "interpreted"
    assert {e.assertion_kind for e in first.evidence} == {"starting_slot", "bench_membership"}
    left = next(e for e in first.evidence if e.player_id == 1002)
    assert (left.position, left.tactical_role, left.side) == ("LAT", "FB", "LEFT")
    assert json.loads(left.details_json)["habitual_role_accepted"] is False
    bench = first.evidence[-1]
    assert bench.position is bench.side is bench.tactical_role is None


@pytest.mark.anyio
async def test_cosmetic_changes_preserve_semantic_identity_but_keep_new_payload_version():
    repo = FakeEvidenceRepository()
    data = lineup()
    await capture(repo, [data])
    before = repo.captures[0]
    data["startXI"][3]["player"]["name"] = "Updated spelling"
    data["startXI"][3]["player"]["sfa_points"] = 987
    data["startXI"].reverse()
    await capture(repo, [data])
    after = repo.captures[0]
    assert before.payload_hash != after.payload_hash
    assert {e.source_hash for e in before.evidence} == {e.source_hash for e in after.evidence}


@pytest.mark.anyio
@pytest.mark.parametrize("issue", ["unsupported", "missing_grid", "duplicate", "cross_team", "duplicate_team"])
async def test_partial_invalid_or_ambiguous_lineups_cannot_invent_roles(issue):
    repo = FakeEvidenceRepository()
    data = [lineup(), lineup(530, 20)]
    if issue == "unsupported":
        data[0]["formation"] = "5-4-1"
    elif issue == "missing_grid":
        data[0]["startXI"][1]["player"]["grid"] = None
    elif issue == "duplicate":
        data[0]["startXI"][1] = data[0]["startXI"][0]
    elif issue == "cross_team":
        data[1]["startXI"][1]["player"]["id"] = 2
    else:
        data.append(data[0])
    await capture(repo, data)
    assert not any(e.tactical_role for e in repo.captures[0].evidence)
    assert repo.captures[0].validation_reason
    assert repo.coverage["both_starting_elevens"] is (issue in {"unsupported", "missing_grid"})


@pytest.mark.anyio
async def test_missing_crosswalk_keeps_unknown_ids_in_coverage_without_false_foreign_keys():
    repo = FakeEvidenceRepository()
    repo.players = {2}
    await capture(repo, [lineup()])
    assert repo.coverage["unresolved_player_ids"] == [2]
    assert repo.coverage["unresolved_starting_player_ids"] == [2]
    assert not any(e.player_id == 1002 for e in repo.captures[0].evidence)


@pytest.mark.anyio
async def test_unmapped_bench_player_does_not_invalidate_known_starting_elevens():
    repo = FakeEvidenceRepository()
    repo.players = {12}
    await capture(repo, [lineup(), lineup(530, 20)])
    assert repo.coverage["unresolved_player_ids"] == [12]
    assert repo.coverage["unresolved_starting_player_ids"] == []
    assert repo.coverage["both_starting_elevens"]


@pytest.mark.anyio
async def test_unknown_fixture_and_provider_error_never_write():
    repo = FakeEvidenceRepository()
    uc = RecordPositionEvidenceUseCase(repo)
    result = await uc.execute(100, '{"errors":{"quota":"limit"}}', "test", "2026-10-18T00:00:00+00:00")
    assert result.status == "provider_error"
    repo.context = None
    result = await capture(repo, [])
    assert result.status == "fixture_not_ingested"
    assert repo.writes == 0


@pytest.mark.anyio
@pytest.mark.parametrize("metadata", [{"parameters": {"fixture": "999"}}, {"fixture": {"external_id": 999}}])
async def test_contradictory_fixture_identity_never_attaches_to_requested_fixture(metadata):
    repo = FakeEvidenceRepository()
    result = await RecordPositionEvidenceUseCase(repo).execute(
        100, json.dumps({**metadata, "response": [lineup()]}), "test", "2026-10-18T12:00:00+00:00",
    )
    assert result.status == "fixture_identity_mismatch"
    assert repo.writes == 0


@pytest.mark.anyio
@pytest.mark.parametrize("malformation", ["null_player", "mixed_duplicate_grid"])
async def test_malformed_lineup_is_preserved_without_roles(malformation):
    repo = FakeEvidenceRepository()
    data = lineup()
    if malformation == "null_player":
        data["startXI"][0] = {"player": None}
    else:
        data["startXI"][1]["player"]["id"] = 1
        data["startXI"][1]["player"]["grid"] = None
    await capture(repo, [data])
    assert repo.captures[0].validation_status == "invalid"
    assert not any(e.tactical_role for e in repo.captures[0].evidence)


@pytest.mark.anyio
async def test_real_normalized_archive_is_supported_without_using_player_names():
    snapshot = json.loads((Path(__file__).parents[1] / "fixtures/player-position-lineups-2026.json").read_text("utf-8"))
    # All actual normalized DTO payloads are retained as a second schema regression.
    assert snapshot["players"]
    repo = FakeEvidenceRepository()
    data = lineup()
    normalized = {"team": {"external_id": 529}, "formation": data["formation"],
                  "start_xi": [{"external_id": p["player"]["id"], "position": p["player"]["pos"],
                                "grid": p["player"]["grid"]} for p in data["startXI"]], "substitutes": []}
    await capture(repo, [normalized])
    assert len(repo.captures[0].evidence) == 11
    assert repo.captures[0].validation_status == "interpreted"
