import hashlib
import json
from dataclasses import replace

import pytest

from sfa.application.use_cases.capture_catalog_lineup_batch import CaptureCatalogLineupBatchUseCase
from sfa.domain.player_positions.ports import LineupEvidenceArchive, LineupEvidenceProvider, LineupEvidenceResponse


@pytest.fixture
def anyio_backend():
    return "asyncio"


def response(identity=None, **changes):
    data = {"active": True} if identity is None else {"parameters": {"fixture": str(identity)}, "errors": [],
        "response": [{"team": {"id": team}, "formation": "4-3-3", "startXI": [], "substitutes": []}
                     for team in (10, 20)]}
    return replace(LineupEvidenceResponse(identity, 200, json.dumps(data), "2026-10-19T12:00:00+00:00",
                                          1000, 100, 300), **changes)


class FakeProvider(LineupEvidenceProvider):
    def __init__(self):
        self.calls, self.responses = [], {}

    async def status(self):
        self.calls.append(None)
        return self.responses.get(None, response())

    async def fetch_lineups(self, fixture_id):
        self.calls.append(fixture_id)
        return self.responses.get(fixture_id, response(fixture_id))


class FakeArchive(LineupEvidenceArchive):
    def __init__(self):
        self.held, self.manifest, self.responses, self.pending = False, None, {}, []

    async def acquire(self):
        assert not self.held
        self.held = True

    async def release(self):
        self.held = False

    async def load_manifest(self):
        return self.manifest

    async def save_manifest(self, content):
        self.manifest = content
        value = json.loads(content)
        if value["requests"] and value["requests"][-1]["state"] == "attempt_started":
            self.pending.append(value["requests"][-1]["fixture_id"])

    async def load_response(self, fixture_id):
        return self.responses.get(fixture_id)

    async def save_response(self, value):
        assert self.pending and self.held
        self.responses[value.fixture_id] = value
        return hashlib.sha256(value.body.encode()).hexdigest()

    async def save_snapshot(self, content):
        raise AssertionError("No publication or derived snapshot write in acquisition")


def fixtures(n=10):
    return tuple({"external_id": i, "played_at": "2026-09-01T12:00:00+00:00",
                  "home_team_external_id": 10, "away_team_external_id": 20} for i in range(1, n + 1))


@pytest.mark.anyio
async def test_batch_cap_checkpoint_and_resume_never_repeat_a_get():
    provider, archive = FakeProvider(), FakeArchive()
    uc = CaptureCatalogLineupBatchUseCase(provider, archive)
    result = await uc.execute(fixtures=fixtures(), input_sha256="frozen")
    assert result.state == "completed" and result.requests == 11
    assert provider.calls == [None] + list(range(1, 11)) and not archive.held
    again = await uc.execute(fixtures=fixtures(), input_sha256="frozen")
    assert again.requests == 11 and len(provider.calls) == 11 and len(json.loads(again.acquired_json)) == 10


@pytest.mark.anyio
@pytest.mark.parametrize("change,state", [({"daily_remaining": None}, "quota_unknown"),
                                          ({"daily_remaining": 100}, "quota_margin_exhausted"),
                                          ({"minute_remaining": 1}, "quota_margin_exhausted"),
                                          ({"http_status": 429}, "http_429")])
async def test_unknown_or_exhausted_quota_stops_before_lineup_requests(change, state):
    provider, archive = FakeProvider(), FakeArchive()
    provider.responses[None] = response(**change)
    uc = CaptureCatalogLineupBatchUseCase(provider, archive)
    result = await uc.execute(fixtures=fixtures(), input_sha256="frozen")
    assert result.state == state and provider.calls == [None] and not archive.held


@pytest.mark.anyio
async def test_provider_error_has_no_retry_and_does_not_request_the_next_fixture():
    provider, archive = FakeProvider(), FakeArchive()
    provider.responses[2] = response(2, http_status=429)
    uc = CaptureCatalogLineupBatchUseCase(provider, archive)
    result = await uc.execute(fixtures=fixtures(), input_sha256="frozen")
    assert result.state == "http_429" and provider.calls == [None, 1, 2]
    resumed = await uc.execute(fixtures=fixtures(), input_sha256="frozen")
    assert resumed.state == "archived_error_requires_review"
    assert provider.calls == [None, 1, 2]


@pytest.mark.anyio
async def test_more_than_ten_or_duplicate_fixtures_rejected_without_network():
    provider, archive = FakeProvider(), FakeArchive()
    uc = CaptureCatalogLineupBatchUseCase(provider, archive)
    for values in (fixtures(11), fixtures(1) * 2, ()):
        with pytest.raises(ValueError):
            await uc.execute(fixtures=values, input_sha256="frozen")
    assert not provider.calls and not archive.held


@pytest.mark.anyio
async def test_changed_input_cannot_reuse_previous_manifest():
    provider, archive = FakeProvider(), FakeArchive()
    uc = CaptureCatalogLineupBatchUseCase(provider, archive)
    await uc.execute(fixtures=fixtures(1), input_sha256="frozen")
    with pytest.raises(ValueError, match="different batch"):
        await uc.execute(fixtures=fixtures(1), input_sha256="other")
    assert provider.calls == [None, 1] and not archive.held


@pytest.mark.anyio
async def test_identity_mismatch_preserves_requested_identity_for_quarantine_without_retry():
    provider, archive = FakeProvider(), FakeArchive()
    provider.responses[1] = response(2)
    uc = CaptureCatalogLineupBatchUseCase(provider, archive)
    result = await uc.execute(fixtures=fixtures(), input_sha256="frozen")
    assert result.state == "fixture_identity_mismatch" and provider.calls == [None, 1]
    record = json.loads(archive.manifest)["requests"][-1]
    assert record["fixture_id"] == 1 and record["response_fixture_id"] == 2
    await uc.execute(fixtures=fixtures(), input_sha256="frozen")
    assert provider.calls == [None, 1]
