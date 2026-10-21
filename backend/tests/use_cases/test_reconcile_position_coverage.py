from __future__ import annotations

import json
from dataclasses import replace

import pytest

from sfa.application.use_cases.reconcile_position_coverage import ReconcilePositionCoverageUseCase
from sfa.domain.player_positions.ports import (
    LineupEvidenceResponse,
    PositionCalendarCoverageState,
    PositionCalendarProvider,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def provider_fixture(fixture_id=1):
    return {"fixture": {"id": fixture_id, "date": "2026-10-01T12:00:00Z", "status": {"short": "FT"}},
            "league": {"id": 140, "season": 2026}, "teams": {"home": {"id": 529}, "away": {"id": 530}}}


class FakeCalendarProvider:
    def __init__(self):
        self.body = {"parameters": {"league": "140", "season": "2026"}, "results": 1,
                     "paging": {"current": 1, "total": 1}, "response": [provider_fixture()]}
        self.quota = LineupEvidenceResponse(None, 200, '{"active":true}', "2026-10-18T12:00:00+00:00",
                                           5000, 250, 300)
        self.calls = []

    async def status(self):
        self.calls.append("status")
        return self.quota

    async def fetch_calendar(self, league_id, season):
        self.calls.append((league_id, season))
        return replace(self.quota, body=json.dumps(self.body))


class FakeCalendarState:
    def __init__(self):
        self.lease = True
        self.owner = True
        self.released = False
        self.rows = [{"external_id": 1, "home_team_external_id": 529, "away_team_external_id": 530,
                      "both_starting_elevens": True, "status": "FT"}]
        self.proofs = []

    async def acquire(self):
        return self.lease

    async def owns_lease(self):
        return self.owner

    async def release(self):
        self.released = True

    async def inventory(self, competition_id, season):
        return json.dumps(self.rows)

    async def record_calendar(self, scope_key, proof_json, status):
        self.proofs.append((scope_key, json.loads(proof_json), status))


def setup():
    provider, state = FakeCalendarProvider(), FakeCalendarState()
    assert isinstance(provider, PositionCalendarProvider)
    assert isinstance(state, PositionCalendarCoverageState)
    return ReconcilePositionCoverageUseCase(provider, state), provider, state


@pytest.mark.anyio
async def test_only_reconciled_calendar_and_both_starting_elevens_establish_scope_completeness():
    uc, provider, state = setup()
    result = await uc.execute(1, 140, "2026")
    assert result["state"] == "complete"
    assert result["calendar_reconciled"]
    assert result["completed_fixture_ids"] == [1]
    assert result["habitual_role_coverage"] == "unknown"
    assert "raw_body" not in result
    assert json.loads(state.proofs[0][1]["raw_body"]) == provider.body
    assert state.released


@pytest.mark.anyio
@pytest.mark.parametrize("case,field", [
    ("not_ingested", "missing_ingestion_ids"), ("missing_lineup", "missing_lineup_ids"),
    ("wrong_teams", "identity_mismatch_ids"), ("local_extra", "local_unlisted_ids"),
])
async def test_inventory_gaps_are_explicit_and_cannot_be_complete(case, field):
    uc, provider, state = setup()
    if case == "not_ingested":
        state.rows = []
    elif case == "missing_lineup":
        state.rows[0]["both_starting_elevens"] = False
    elif case == "wrong_teams":
        state.rows[0]["away_team_external_id"] = 999
    else:
        state.rows.append({**state.rows[0], "external_id": 2})
    result = await uc.execute(1, 140, "2026")
    assert result["state"] == "partial"
    assert result[field]


@pytest.mark.anyio
@pytest.mark.parametrize("case", ["paging", "wrong_season", "duplicate", "wrong_league", "missing_parameters"])
async def test_changed_or_ambiguous_provider_contract_never_proves_complete_coverage(case):
    uc, provider, state = setup()
    if case == "paging":
        provider.body["paging"]["total"] = 2
    elif case == "wrong_season":
        provider.body["response"][0]["league"]["season"] = 2025
    elif case == "wrong_league":
        provider.body["parameters"]["league"] = "39"
    elif case == "duplicate":
        provider.body["response"].append(provider_fixture())
        provider.body["results"] = 2
    else:
        provider.body.pop("parameters")
    result = await uc.execute(1, 140, "2026")
    assert result["state"] == "invalid"
    assert not result["calendar_reconciled"]
    assert state.released


@pytest.mark.anyio
async def test_empty_calendar_does_not_become_full_player_coverage():
    uc, provider, state = setup()
    provider.body["response"] = []
    provider.body["results"] = 0
    state.rows = []
    result = await uc.execute(1, 140, "2026")
    assert result["state"] == "partial"
    assert result["empty_scope"]


@pytest.mark.anyio
async def test_calendar_quota_and_lease_are_shared_with_collector():
    uc, provider, state = setup()
    state.lease = False
    assert (await uc.execute(1, 140, "2026"))["state"] == "lease_busy"
    assert provider.calls == []
    state.lease = True
    provider.quota = replace(provider.quota, daily_remaining=100)
    assert (await uc.execute(1, 140, "2026"))["state"] == "quota_unavailable"
    assert provider.calls == ["status"]
