from __future__ import annotations

import json
from dataclasses import replace

import pytest

from sfa.application.use_cases.collect_position_lineups import CollectPositionLineupsUseCase
from sfa.domain.player_positions.ports import (
    LineupEvidenceProvider,
    LineupEvidenceResponse,
    PositionEvidenceRecorder,
    PositionLineupCollectionState,
    RecordPositionEvidenceResult,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def response(fixture_id=None, **overrides):
    value = LineupEvidenceResponse(
        fixture_id, 200, json.dumps({"active": True}) if fixture_id is None else '{"response":[]}',
        "2026-10-18T12:00:00+00:00", 5000, 250, 300,
    )
    return replace(value, **overrides)


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.quota = response()
        self.results = {}

    async def status(self):
        self.calls.append(None)
        return self.quota

    async def fetch_lineups(self, fixture_id):
        self.calls.append(fixture_id)
        return self.results.get(fixture_id, response(fixture_id))


class FakeState:
    def __init__(self):
        self.lease_available = True
        self.owner = True
        self.fixtures = (101, 102)
        self.checkpoints = []
        self.released = False

    async def acquire(self):
        return self.lease_available

    async def owns_lease(self):
        return self.owner

    async def release(self):
        self.released = True

    async def pending(self, season, limit):
        return self.fixtures[:limit]

    async def checkpoint(self, fixture_id, state, details_json):
        self.checkpoints.append((fixture_id, state, json.loads(details_json)))


class FakeRecorder:
    def __init__(self):
        self.calls = []
        self.status = "recorded"

    async def execute(self, fixture_external_id, payload_json, source_ref, received_at):
        self.calls.append(fixture_external_id)
        return RecordPositionEvidenceResult(fixture_external_id, 0, 0, self.status)


def setup():
    provider, recorder, state = FakeProvider(), FakeRecorder(), FakeState()
    assert isinstance(provider, LineupEvidenceProvider)
    assert isinstance(recorder, PositionEvidenceRecorder)
    assert isinstance(state, PositionLineupCollectionState)
    return CollectPositionLineupsUseCase(provider, recorder, state), provider, recorder, state


@pytest.mark.anyio
async def test_bounded_capture_checkpoints_attempt_before_each_request_and_releases():
    uc, provider, recorder, state = setup()
    report = await uc.execute("2026")
    assert report["http_calls"] == 3
    assert provider.calls == [None, 101, 102]
    assert recorder.calls == [101, 102]
    assert [(f, s) for f, s, _ in state.checkpoints] == [
        (None, "attempt_started"), (None, "response"),
        (101, "attempt_started"), (101, "response"), (102, "attempt_started"), (102, "response"),
    ]
    assert report["state"] == "batch_complete"
    assert report["calendar_coverage"] == "unknown"
    assert state.released


@pytest.mark.anyio
@pytest.mark.parametrize("reason", ["lease_busy", "no_known_missing_fixtures", "lease_lost"])
async def test_no_requests_without_work_or_ownership(reason):
    uc, provider, recorder, state = setup()
    if reason == "lease_busy":
        state.lease_available = False
    elif reason == "no_known_missing_fixtures":
        state.fixtures = ()
    else:
        state.owner = False
    report = await uc.execute("2026")
    assert report["state"] == reason
    assert provider.calls == ([None] if reason == "lease_lost" else [])
    assert recorder.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize("quota,expected", [
    ({"daily_remaining": 100}, "daily_quota_reserve"),
    ({"daily_remaining": None}, "daily_quota_reserve"),
    ({"minute_remaining": 2}, "minute_quota_reserve"),
    ({"minute_remaining": None}, "minute_quota_reserve"),
])
async def test_unknown_or_low_quota_prevents_lineup_http(quota, expected):
    uc, provider, recorder, state = setup()
    provider.quota = response(**quota)
    report = await uc.execute("2026")
    assert report["state"] == expected
    assert provider.calls == [None]
    assert recorder.calls == []
    assert state.released


@pytest.mark.anyio
@pytest.mark.parametrize("failure,expected", [
    ({"http_status": 429}, "http_429"),
    ({"transport_error": "ReadTimeout"}, "ReadTimeout"),
    ({"body": '{"errors":{"quota":"exceeded"}}'}, "provider_error"),
    ({"body": "broken"}, "invalid_json"),
    ({"fixture_id": 999}, "fixture_identity_mismatch"),
])
async def test_first_error_stops_without_retry_or_publication(failure, expected):
    uc, provider, recorder, state = setup()
    provider.results[101] = replace(response(101), **failure)
    report = await uc.execute("2026")
    assert report["state"] == expected
    assert provider.calls == [None, 101]
    assert recorder.calls == []
    assert state.checkpoints[-1][1] == "response"
    assert state.released


@pytest.mark.anyio
async def test_response_headers_reduce_remaining_budget_before_next_fixture():
    uc, provider, recorder, state = setup()
    provider.results[101] = response(101, daily_remaining=100)
    report = await uc.execute("2026")
    assert report["state"] == "daily_quota_reserve"
    assert recorder.calls == [101]
    assert provider.calls == [None, 101]


@pytest.mark.anyio
async def test_invalid_capture_stops_batch_even_when_transport_succeeded():
    uc, provider, recorder, state = setup()
    recorder.status = "fixture_identity_mismatch"
    report = await uc.execute("2026")
    assert report["state"] == "fixture_identity_mismatch"
    assert provider.calls == [None, 101]


@pytest.mark.anyio
async def test_budget_is_hard_capped_to_ten_fixture_requests():
    uc, provider, recorder, state = setup()
    state.fixtures = tuple(range(100, 130))
    result = await uc.execute("2026", 10)
    assert result["http_calls"] == 11
    with pytest.raises(ValueError):
        await uc.execute("2026", 11)
