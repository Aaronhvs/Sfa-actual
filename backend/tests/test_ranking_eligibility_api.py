import httpx
import pytest
from fastapi import FastAPI

from sfa.api.v1.ranking import router
from sfa.application.use_cases.get_ranking import RankingPagination, RankingResult
from sfa.core.dependencies import get_ranking_use_case
from sfa.domain.ports import RankedPlayerDTO


@pytest.mark.anyio
@pytest.mark.parametrize("minimum,with_player", [(0, True), (1, False), (3, True), (5, False)])
async def test_http_response_always_exposes_applied_minimum(minimum, with_player):
    player = RankedPlayerDTO(1, 42, "Player", "Club", None, "DEL", "League", 100, 3, None)

    class Ranking:
        async def execute(self, **kwargs):
            total = int(with_player)
            return RankingResult("2026", "season-2026", total, [player] if with_player else [],
                                 RankingPagination(1, 10, total, total, False, False), minimum)

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_ranking_use_case] = lambda: Ranking()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        response = await client.get("/api/v1/ranking?scope=season-2026")
    assert response.status_code == 200
    body = response.json()
    assert body["min_matches"] == minimum
    assert body["total"] == body["pagination"]["total_items"] == len(body["ranking"])
    if with_player:
        assert body["ranking"][0]["sfa_pts"] == 100
