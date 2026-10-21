"""Read-side regression matrix against an explicitly restored PostgreSQL clone.

No provider or model writer is called. Set POSITION_VALIDATION_CLONE=1 only with
DATABASE_URL targeting the restored validation database.
"""
from __future__ import annotations

import os

import httpx
import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.anyio, pytest.mark.skipif(os.getenv("POSITION_VALIDATION_CLONE") != "1",
                                                   reason="Requires restored position-validation PostgreSQL clone")]


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def client():
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.main import app

    async with AsyncSessionLocal() as session:
        assert (await session.scalar(text("SELECT current_database()"))).startswith("sfa_positions_validation_")
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://validation")


@pytest.mark.parametrize("scope", ["season-2026", "season-2025", "world-cup-2026", "all"])
async def test_ranking_projection_filters_and_count_agree_before_pagination(scope):
    async with await client() as http:
        for position in ("DEL", "EXT", "MC", "MCO", "LAT", "DC"):
            response = await http.get("/api/v1/ranking", params={"scope": scope, "position": position, "limit": 5})
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["pagination"]["total_items"] == data["total"]
            assert all(r["position"] == position for r in data["ranking"])
            assert len(data["ranking"]) == min(5, data["total"])
            if data["total"] > 5:
                page2 = (await http.get("/api/v1/ranking", params={
                    "scope": scope, "position": position, "limit": 5, "page": 2})).json()
                assert not {r["id"] for r in data["ranking"]} & {r["id"] for r in page2["ranking"]}
                assert len(page2["ranking"]) == min(5, data["total"] - 5)


@pytest.mark.parametrize("profile", ["Promesa", "Veterano", "Goleador", "Asistidor"])
async def test_ranking_search_profiles_are_consistent_with_public_statistics(profile):
    async with await client() as http:
        for scope in ("season-2026", "all"):
            response = await http.get("/api/v1/ranking", params={
                "scope": scope, "bonus_label": profile, "competition_id": 1, "limit": 5, "name": "Barcelona"})
            assert response.status_code == 200, response.text
            data = response.json()
            assert all(r["team"] == "Barcelona" for r in data["ranking"])
            assert len(data["ranking"]) <= data["total"]
            if profile in {"Goleador", "Asistidor"}:
                key = "goals" if profile == "Goleador" else "assists"
                assert all(r[key] >= 1 for r in data["ranking"])


@pytest.mark.parametrize("player_id", [35, 52, 517, 75])
async def test_player_detail_history_and_comparison_share_scoped_data(player_id):
    async with await client() as http:
        detail = await http.get(f"/api/v1/players/{player_id}", params={"scope": "season-2026"})
        assert detail.status_code == 200, detail.text
        data = detail.json()
        assert data["id"] == player_id
        if player_id in {52, 517}:
            assert data["position"] == "MCO"
        for suffix in ("events", "stats", "fixtures", "achievements", "individual-honors"):
            result = await http.get(f"/api/v1/players/{player_id}/{suffix}", params={"scope": "season-2026"})
            assert result.status_code == 200, result.text
        comparison = await http.get("/api/v1/compare", params={"player_a": player_id,
                                                              "player_b": 52 if player_id == 35 else 35,
                                                              "scope": "season-2026"})
        assert comparison.status_code == 200, comparison.text
        # No unknown position or null score may be introduced by the new SQL projection.
        assert data["position"] in {"DEL", "EXT", "MCO", "MC", "LAT", "DC", "GK"}


async def test_historical_and_all_time_player_contracts_remain_readable():
    async with await client() as http:
        for params in ({"season": "2026"}, {"scope": "world-cup-2026"}, {"season": "all"}):
            for path in ("/players/35", "/players/35/events", "/players/35/fixtures", "/players/35/stats"):
                response = await http.get("/api/v1" + path, params=params)
                assert response.status_code == 200, response.text
        response = await http.get("/api/v1/players/999999999")
        assert response.status_code == 404


async def test_competitions_tournaments_and_team_rankings_remain_available():
    async with await client() as http:
        for path, params in (
            ("/seasons", {}), ("/competitions", {}),
            ("/tournaments", {"season": "2026"}), ("/tournaments/1", {"season": "2026"}),
            ("/tournaments/dashboard", {"season": "2026", "date": "2026-10-17"}),
            ("/teams/ranking", {"season": "2026", "name": "Barcelona"}),
            ("/teams/ranking", {"season": "2026", "participant_kind": "national"}),
            ("/ranking/explanations", {"season": "2026", "scope_key": "season-2026"}),
        ):
            response = await http.get("/api/v1" + path, params=params)
            assert response.status_code == 200, (path, response.text)


async def test_explanation_evidence_uses_persisted_scores_and_resolved_positions():
    from sfa.domain.ranking_explanation_ports import RankingExplanationRequestDTO
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.repositories.ranking_explanation_repository import RankingExplanationRepository
    from sfa.infrastructure.repositories.season_repository import SeasonRepository
    from sfa.infrastructure.repositories.sfa_score_repository import SFAScoreRepository

    async with AsyncSessionLocal() as session:
        assert (await session.scalar(text("SELECT current_database()"))).startswith("sfa_positions_validation_")
        scores, explanations = SFAScoreRepository(session), RankingExplanationRepository(session)
        for key in ("season-2026", "world-cup-2026", "all"):
            scope = None if key == "all" else await SeasonRepository(session).resolve_scope(key)
            players = (await scores.get_ranking_for_scope(scope, limit=3, rules_version_id=4) if scope
                       else await scores.get_ranking_all_seasons(limit=3, rules_version_id=4))
            assert players
            request = RankingExplanationRequestDTO("2026" if scope else "all", None, 4, "ranking", scope_key=key)
            first = await explanations.build_evidence(request, players, source_scope=scope)
            assert {e.player_id for e in first} == {p.player_id for p in players}
            assert all(len(e.source_hash) == 64 and e.evidence for e in first)
            ranked = {p.player_id: p for p in players}
            for evidence in first:
                player = evidence.evidence["player"]
                assert player["position"] == ranked[evidence.player_id].position
                assert player["total_pts"] == round(ranked[evidence.player_id].total_pts, 2)
