from datetime import datetime, timezone

import httpx
import pytest
from fastapi import FastAPI

from sfa.api.v1.tournaments import router
from sfa.application.use_cases.get_latest_tournament_mvps import GetLatestTournamentMvpsResult, LatestTournamentMvp
from sfa.application.use_cases.get_tournament_mvps import GetTournamentMvpsResult
from sfa.core.dependencies import get_latest_tournament_mvps_use_case, get_tournament_mvps_use_case
from sfa.domain.matchday_mvp import MatchdayMvp, MvpFixture, MvpPlayer
from sfa.domain.ports import TournamentCompetitionDTO, TournamentTeamDTO
from sfa.domain.season_scope import InconsistentScopeRulesVersionError

TEAM = TournamentTeamDTO(1, 529, "Barcelona")
ITEM = MatchdayMvp("matchday-9", "Jornada 9", 9, False, 1,
                   MvpPlayer(34, "Lamine Yamal", "Barcelona", "EXT", None), 3139.0, 1, 2,
                   ("big_rival", "behind"),
                   MvpFixture(1234567, datetime(2026, 9, 9, 19, tzinfo=timezone.utc), TEAM,
                              TournamentTeamDTO(9, 209, "Feyenoord"), 3, 1, "home"))
COMPETITION = TournamentCompetitionDTO(1, "La Liga", "ES", "2026", "club", 380, 90, 290)


class FakeTournamentUseCase:
    async def execute(self, competition_id, season=None):
        if competition_id == 999:
            raise ValueError("Competition not found")
        if season == "2025":
            raise InconsistentScopeRulesVersionError("season-2025")
        return GetTournamentMvpsResult(competition_id, season or "2026", (ITEM,) if season != "1900" else ())


class FakeLatestUseCase:
    async def execute(self, season=None):
        if season == "2025":
            raise InconsistentScopeRulesVersionError("season-2025")
        return GetLatestTournamentMvpsResult(season or "2026", (LatestTournamentMvp(COMPETITION, ITEM),)
                                             if season != "1900" else ())


async def request(path):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_tournament_mvps_use_case] = FakeTournamentUseCase
    app.dependency_overrides[get_latest_tournament_mvps_use_case] = FakeLatestUseCase
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.anyio
async def test_exact_contract_and_static_route():
    body = (await request("/api/v1/tournaments/1/mvps?season=2026")).json()
    assert set(body) == {"competition_id", "season", "items"}
    item, = body["items"]
    assert set(item) == {"round_key", "round_label", "matchday", "complete", "pending_fixtures", "player", "sfa_pts",
                         "goals", "assists", "reasons", "fixture"}
    assert item["player"] == {"id": 34, "name": "Lamine Yamal", "team": "Barcelona", "position": "EXT",
                              "photo_url": None}
    assert item["fixture"] == {"external_id": 1234567, "played_at": "2026-09-09T19:00:00Z",
                               "home_team": {"id": 1, "external_id": 529, "name": "Barcelona"},
                               "away_team": {"id": 9, "external_id": 209, "name": "Feyenoord"},
                               "home_goals": 3, "away_goals": 1, "player_side": "home"}
    assert item["reasons"] == ["big_rival", "behind"]
    latest = await request("/api/v1/tournaments/mvps/latest?season=2026")
    assert latest.status_code == 200
    assert set(latest.json()) == {"season", "items"}
    assert latest.json()["items"][0]["mvp"] == item
    assert set(latest.json()["items"][0]["competition"]) == {
        "id", "name", "country", "season", "participant_kind", "total_fixtures", "completed_fixtures",
        "upcoming_fixtures"}


@pytest.mark.anyio
async def test_empty_unknown_invalid_and_conflict_statuses():
    for path in ("1/mvps", "mvps/latest"):
        assert (await request(f"/api/v1/tournaments/{path}?season=1900")).json()["items"] == []
        assert (await request(f"/api/v1/tournaments/{path}?season=bad")).status_code == 422
        assert (await request(f"/api/v1/tournaments/{path}?season=2025")).status_code == 409
    assert (await request("/api/v1/tournaments/999/mvps?season=2026")).status_code == 404
    assert (await request("/api/v1/tournaments/0/mvps?season=2026")).status_code == 422
