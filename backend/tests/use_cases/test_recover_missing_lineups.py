import hashlib
import json
from copy import deepcopy
from dataclasses import replace

import pytest

from sfa.application.use_cases.recover_missing_lineups import RecoverMissingLineupsUseCase
from sfa.domain.player_positions.ports import (
    LineupEvidenceArchive,
    LineupEvidenceProvider,
    LineupEvidenceResponse,
    PositionAuditSnapshotSource,
)
from sfa.domain.player_positions.value_objects import PositionAuditSnapshot


@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_data(total=4, cache_last=True):
    fixtures = [{"external_id": i, "season": "2026", "competition_id": 1,
                 "home_team_external_id": 10, "away_team_external_id": 20, "status": "FT",
                 "played_at": f"2026-09-{i:02d}T12:00:00+00:00"} for i in range(1, total + 1)]
    return {"schema": "sfa-position-audit-snapshot-v1", "read_only": True, "season": "2026",
            "captured_at": "2026-10-18T12:00:00+00:00", "players": [], "fixtures": fixtures,
            "cache": [{"key": f"fixture:api:supplement:v2:{total}", "payload": {
                "fixture": {"external_id": total}, "lineups": [{"team": {"external_id": 10},
                                                                            "start_xi": [{"external_id": 1}]}]}}
                      ] if cache_last else []}


def response(identity=None, **changes):
    body = {"active": True, "errors": False} if identity is None else {
        "parameters": {"fixture": str(identity)}, "errors": [], "response": [
            {"team": {"id": team}, "formation": "4-3-3", "startXI": [], "substitutes": []}
            for team in (10, 20)]}
    return replace(LineupEvidenceResponse(identity, 200, json.dumps(body), "2026-10-18T12:01:00+00:00",
                                          1000, 100, 300), **changes)


class FakeSnapshot(PositionAuditSnapshotSource):
    def __init__(self, data):
        self.content = json.dumps(data)

    async def load(self):
        return PositionAuditSnapshot(self.content, hashlib.sha256(self.content.encode()).hexdigest())


class FakeProvider(LineupEvidenceProvider):
    def __init__(self):
        self.calls = []
        self.status_response = response()
        self.responses = {}

    async def status(self):
        self.calls.append(None)
        return self.status_response

    async def fetch_lineups(self, fixture_id):
        self.calls.append(fixture_id)
        return self.responses.get(fixture_id, response(fixture_id))


class FakeArchive(LineupEvidenceArchive):
    def __init__(self):
        self.manifest = None
        self.responses = {}
        self.snapshot = None
        self.checkpoints = []
        self.held = False

    async def acquire(self):
        if self.held:
            raise RuntimeError("Archive is already held")
        self.held = True

    async def release(self):
        self.held = False

    async def load_manifest(self):
        return self.manifest

    async def save_manifest(self, content):
        self.manifest = content
        self.checkpoints.append(json.loads(content))

    async def load_response(self, fixture_id):
        return self.responses.get(fixture_id)

    async def save_response(self, value):
        self.responses[value.fixture_id] = value
        return hashlib.sha256(value.body.encode()).hexdigest()

    async def save_snapshot(self, content):
        self.snapshot = content


async def run(data=None, provider=None, archive=None, **kwargs):
    provider = provider or FakeProvider()
    archive = archive or FakeArchive()
    source = FakeSnapshot(data or make_data())
    assert isinstance(source, PositionAuditSnapshotSource)
    assert isinstance(provider, LineupEvidenceProvider)
    assert isinstance(archive, LineupEvidenceArchive)
    result = await RecoverMissingLineupsUseCase(source, provider, archive).execute(
        season="2026", team_external_id=10, **kwargs)
    return json.loads(result.summary_json), provider, archive


@pytest.mark.anyio
async def test_recovers_only_missing_known_fixtures_and_resumes_without_any_http():
    data = make_data()
    original = deepcopy(data)
    result, provider, archive = await run(data)
    assert data == original and provider.calls == [None, 1, 2, 3]
    assert result["state"] == "completed" and result["http_calls_this_execution"] == 4
    assert result["acquisition"]["lineup_calls"] == 3
    assert result["already_preserved_fixture_ids"] == [4]
    first_snapshot = archive.snapshot
    overlay = json.loads(first_snapshot)
    assert overlay["starter_denominator_available"] is False and len(overlay["cache"]) == 4
    pending_checkpoints = [checkpoint["requests"][-1]["fixture_id"] for checkpoint in archive.checkpoints
                           if checkpoint["requests"] and checkpoint["requests"][-1]["state"] == "attempt_started"]
    assert pending_checkpoints == [None, 1, 2, 3]
    replay, _, _ = await run(data, provider, archive)
    assert replay["http_calls_this_execution"] == 0 and provider.calls == [None, 1, 2, 3]
    assert archive.snapshot == first_snapshot


@pytest.mark.anyio
async def test_latest_ten_cap_excludes_other_teams_future_and_non_completed():
    data = make_data(total=15, cache_last=False)
    data["fixtures"] += [{**data["fixtures"][0], "external_id": 99, "status": "NS"},
                         {**data["fixtures"][0], "external_id": 98, "home_team_external_id": 30},
                         {**data["fixtures"][0], "external_id": 97, "played_at": "2027-01-01T12:00:00+00:00"}]
    result, provider, _ = await run(data)
    assert result["selected_fixture_ids"] == list(range(6, 16))
    assert provider.calls == [None] + list(range(6, 16)) and result["http_calls_this_execution"] == 11
    assert result["not_selected_missing_fixture_ids"] == list(range(5, 0, -1))


@pytest.mark.anyio
async def test_no_missing_evidence_does_not_even_check_status():
    result, provider, _ = await run(make_data(total=1))
    assert not provider.calls and not result["selected_fixture_ids"]


@pytest.mark.anyio
@pytest.mark.parametrize("changes,state", [
    ({"daily_remaining": None}, "quota_unknown"), ({"minute_remaining": None}, "quota_unknown"),
    ({"minute_limit": None}, "quota_unknown"), ({"daily_remaining": 100}, "quota_margin_exhausted"),
    ({"minute_remaining": 1}, "quota_margin_exhausted"), ({"minute_limit": 0}, "quota_margin_exhausted"),
    ({"http_status": 403}, "http_403"), ({"body": '{"active":false}'}, "access_unavailable"),
    ({"body": "invalid-json"}, "unsupported_schema"),
])
async def test_stops_when_quota_access_or_status_contract_is_unknown(changes, state):
    provider = FakeProvider()
    provider.status_response = response(**changes)
    result, _, _ = await run(provider=provider)
    assert provider.calls == [None] and result["state"] == state
    assert all(value == "not_attempted" for value in result["fixtures"].values())


@pytest.mark.anyio
@pytest.mark.parametrize("changes,state", [
    ({"http_status": 429}, "http_429"), ({"http_status": 503}, "http_503"),
    ({"transport_error": "ReadTimeout"}, "ReadTimeout"),
    ({"body": '{"errors":{"limit":"exhausted"}}'}, "provider_error"),
    ({"body": '{"response":{},"errors":[]}'}, "unsupported_schema"),
    ({"fixture_id": 999}, "fixture_identity_mismatch"),
])
async def test_first_error_stops_batch_and_archived_error_is_not_implicitly_retried(changes, state):
    provider = FakeProvider()
    provider.responses[1] = response(1, **changes)
    result, _, archive = await run(provider=provider)
    assert provider.calls == [None, 1] and result["state"] == state
    assert result["fixtures"]["2"] == "not_attempted"
    replay, _, _ = await run(provider=provider, archive=archive)
    assert replay["http_calls_this_execution"] == 0 and len(provider.calls) == 2


@pytest.mark.anyio
async def test_empty_response_is_preserved_missing_and_never_becomes_a_bench_inference():
    provider = FakeProvider()
    provider.responses[1] = response(1, body='{"response":[],"errors":[]}')
    result, _, archive = await run(provider=provider)
    assert result["fixtures"]["1"] == "provider_empty" and result["state"] == "completed"
    assert len(json.loads(archive.snapshot)["cache"]) == 3
    replay, _, _ = await run(provider=provider, archive=archive)
    assert replay["http_calls_this_execution"] == 0


@pytest.mark.anyio
async def test_rechecks_quota_headers_after_every_response():
    provider = FakeProvider()
    provider.responses[1] = response(1, daily_remaining=100)
    result, _, _ = await run(provider=provider)
    assert provider.calls == [None, 1] and result["state"] == "quota_margin_exhausted"


@pytest.mark.anyio
async def test_different_input_cannot_silently_reuse_the_same_run():
    _, provider, archive = await run()
    with pytest.raises(ValueError, match="different input/selection"):
        await run(make_data(total=5), provider, archive)


@pytest.mark.anyio
@pytest.mark.parametrize("max_fixtures", [0, 11, True])
async def test_rejects_unbounded_or_invalid_batches(max_fixtures):
    with pytest.raises(ValueError, match="batch"):
        await run(max_fixtures=max_fixtures)


@pytest.mark.anyio
async def test_uncertain_interrupted_attempt_is_not_repeated_automatically():
    _, provider, archive = await run()
    manifest = json.loads(archive.manifest)
    manifest["requests"][0]["state"] = "attempt_started"
    archive.manifest = json.dumps(manifest)
    archive.responses.pop(2)
    result, _, _ = await run(provider=provider, archive=archive)
    assert result["state"] == "uncertain_previous_attempt" and result["http_calls_this_execution"] == 0


@pytest.mark.anyio
async def test_supplements_partial_cache_without_discarding_known_assertions():
    data = make_data(total=1, cache_last=False)
    data["cache"] = [{"key": "fixture:api:supplement:v2:1", "payload": {
        "fixture": {"external_id": 1}, "lineups": [{"team": {"external_id": 20}, "formation": "4-3-3",
                                                    "start_xi": []}]}}]
    _, _, archive = await run(data)
    overlay = json.loads(archive.snapshot)
    assert len(overlay["cache"]) == 1 and len(overlay["previous_incomplete_cache"]) == 1
    assert {lineup["team"]["external_id"] for lineup in overlay["cache"][0]["payload"]["lineups"]} == {10, 20}


@pytest.mark.anyio
async def test_conflicting_partial_cache_preserves_both_versions_for_auditor_quarantine():
    data = make_data(total=1, cache_last=False)
    data["cache"] = [{"key": "fixture:api:supplement:v2:1", "payload": {
        "fixture": {"external_id": 1}, "lineups": [{"team": {"external_id": 20}, "formation": "4-4-2",
                                                    "start_xi": []}]}}]
    _, _, archive = await run(data)
    overlay = json.loads(archive.snapshot)
    assert len(overlay["cache"]) == 2 and overlay["previous_incomplete_cache"] == []


@pytest.mark.anyio
async def test_an_existing_archive_lock_prevents_all_provider_calls():
    provider, archive = FakeProvider(), FakeArchive()
    archive.held = True
    with pytest.raises(RuntimeError, match="already held"):
        await run(provider=provider, archive=archive)
    assert provider.calls == []
