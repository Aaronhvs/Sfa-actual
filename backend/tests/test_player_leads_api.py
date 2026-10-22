import httpx
import pytest
from fastapi import FastAPI

from sfa.api.v1.players import router
from sfa.application.use_cases.get_player_leads import GetPlayerLeadsResult
from sfa.core.dependencies import get_player_leads_use_case
from sfa.domain.player_leads import (
    LeadGroup,
    LeadGroupKind,
    LeadMethod,
    LeadMetric,
    LeadThreshold,
    PlayerLead,
)
from sfa.domain.season_scope import ScopeNotFoundError

LEAD = PlayerLead(
    LeadMetric.SHOT_CONVERSION, LeadGroup(LeadGroupKind.COMPETITION, "2025", 140, "La Liga"), 1, False, 38,
    14 / 19, 0.51207, LeadMethod.WILSON_LOWER_BOUND, 14, 19, LeadThreshold(1026, 8, "shots_on_target", 3),
    {"goals": 16, "shots_on": 21, "penalty_goals_excluded": 2},
)


class FakeUseCase:
    def __init__(self, items=(LEAD,), supported=True):
        self.items, self.supported, self.calls = items, supported, []

    async def execute(self, player_id, scope_key=None, max_rank=3, limit=3):
        self.calls.append((player_id, scope_key, max_rank, limit))
        if scope_key == "season-1900":
            raise ScopeNotFoundError(scope_key)
        return GetPlayerLeadsResult(player_id, scope_key, "2025/26", self.supported, "leads-v1", 7,
                                    self.items if self.supported else ())


async def _get(path, use_case):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_player_leads_use_case] = lambda: use_case
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.anyio
async def test_returns_contract_with_items_and_cache_header():
    use_case = FakeUseCase()
    response = await _get("/api/v1/players/35/leads?scope=season-2025&max_rank=2&limit=1", use_case)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300"
    body = response.json()
    assert body["supported"] and body["policy_version"] == "leads-v1" and body["scope"] == "season-2025"
    item = body["items"][0]
    assert item["metric"] == "shot_conversion" and item["rank"] == 1 and item["percentile"] == 1
    assert item["group"] == {"kind": "competition", "season": "2025", "competition_id": 140,
                             "competition_name": "La Liga", "position": None}
    assert item["numerator"] == 14 and item["denominator"] == 19 and item["value"] == pytest.approx(0.7368)
    assert item["minimums"] == {"minutes": 1026, "attempts": 8, "attempts_kind": "shots_on_target", "events": 3}
    assert item["details"]["penalty_goals_excluded"] == 2
    assert use_case.calls == [(35, "season-2025", 2, 1)]


@pytest.mark.anyio
async def test_empty_and_unsupported():
    assert (await _get("/api/v1/players/35/leads", FakeUseCase(items=()))).json()["items"] == []
    body = (await _get("/api/v1/players/35/leads?scope=all", FakeUseCase(supported=False))).json()
    assert body["supported"] is False and body["items"] == []


@pytest.mark.anyio
async def test_unknown_scope_is_404_and_out_of_range_is_422():
    assert (await _get("/api/v1/players/35/leads?scope=season-1900", FakeUseCase())).status_code == 404
    assert (await _get("/api/v1/players/35/leads?max_rank=4", FakeUseCase())).status_code == 422
    assert (await _get("/api/v1/players/35/leads?limit=6", FakeUseCase())).status_code == 422
