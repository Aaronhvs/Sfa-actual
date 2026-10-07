import pytest
from httpx import ASGITransport, AsyncClient

from sfa.application.use_cases.get_team_ranking import GetTeamRankingUseCase
from sfa.core.dependencies import get_team_ranking_use_case
from sfa.domain.team_ranking_ports import TeamRankingDataDTO, TeamRankingInputDTO, TeamRankingRepositoryProtocol
from sfa.main import app


class FakeHttpRankingRepository(TeamRankingRepositoryProtocol):
    async def latest_season(self, participant_kind):
        return "2026"

    async def get_ranking_data(self, season, prior_season, participant_kind, as_of, recent_matches):
        return TeamRankingDataDTO(teams=(TeamRankingInputDTO(1, "Arsenal", 42, 3, "Premier League", (3,)),))


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def ranking_app():
    async def override():
        return GetTeamRankingUseCase(FakeHttpRankingRepository())

    app.dependency_overrides[get_team_ranking_use_case] = override
    yield app
    app.dependency_overrides.pop(get_team_ranking_use_case, None)


@pytest.mark.anyio
async def test_public_route_serializes_nullable_provenance_and_metadata(ranking_app):
    async with AsyncClient(transport=ASGITransport(app=ranking_app), base_url="http://test") as client:
        response = await client.get("/api/v1/teams/ranking?scope=season-2026")
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "season-2026" and body["season"] == "2026"
    assert body["total"] == body["pagination"]["total_items"] == 1
    assert body["ranking"][0]["score"] is None
    assert body["ranking"][0]["availability"] is None
    assert body["ranking"][0]["elo_data_cutoff"] is None
    assert body["model"]["experimental"] is True and body["model"]["feeds_m1"] is False
    assert body["model"]["data_cutoff"] is None


@pytest.mark.anyio
@pytest.mark.parametrize("query", [
    "season=2026&scope=season-2026", "scope=all", "scope=world-cup-2026", "season=2026-29",
    "season=", "page=0", "limit=0", "limit=51", "participant_kind=unknown", "competition_id=0",
])
async def test_route_validates_queries(ranking_app, query):
    async with AsyncClient(transport=ASGITransport(app=ranking_app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/teams/ranking?{query}")
    assert response.status_code == 422


@pytest.mark.anyio
async def test_filter_empty_and_page_overrun_keep_total(ranking_app):
    async with AsyncClient(transport=ASGITransport(app=ranking_app), base_url="http://test") as client:
        filtered = (await client.get("/api/v1/teams/ranking?name=nobody")).json()
        page = (await client.get("/api/v1/teams/ranking?page=2")).json()
    assert filtered["ranking"] == [] and filtered["total"] == 0
    assert page["ranking"] == [] and page["total"] == 1


@pytest.mark.anyio
@pytest.mark.parametrize("alias", ["national", "national_team"])
async def test_national_aliases_expose_canonical_participant_kind(ranking_app, alias):
    async with AsyncClient(transport=ASGITransport(app=ranking_app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/teams/ranking?season=2026&participant_kind={alias}")
    assert response.status_code == 200
    assert response.json()["model"]["participant_kind"] == "national_team"
