"""Exercise staged API code against real data in an enforced read-only transaction."""

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter

from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select, text

from sfa.core.dependencies import get_db
from sfa.infrastructure.database import AsyncSessionLocal, engine
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.repositories.team_ranking_repository import TeamRankingRepository
from sfa.main import app


async def verify_enrichment(session, body):
    as_of = datetime.fromisoformat(body["model"]["as_of"].replace("Z", "+00:00"))
    season = body["season"]
    prior = str(int(season) - 1)
    data = await TeamRankingRepository(session).get_ranking_data(
        season, prior, body["model"]["participant_kind"], as_of, 10,
    )
    fixture_ids = {match["fixture_external_id"] for team in body["ranking"] for match in team["recent_results"]}
    fixtures = {}
    if fixture_ids:
        rows = (await session.execute(
            select(Fixture.external_id, Fixture.id, Fixture.season, Fixture.played_at, Fixture.status,
                   Fixture.home_team_id, Fixture.away_team_id, Fixture.home_goals, Fixture.away_goals,
                   Competition.participant_kind)
            .join(Competition, Competition.id == Fixture.competition_id)
            .where(Fixture.external_id.in_(fixture_ids)),
        )).mappings().all()
        fixtures = {row["external_id"]: row for row in rows}
    for team in body["ranking"]:
        matches = team["recent_results"]
        assert len(matches) <= 5 and len({m["fixture_external_id"] for m in matches}) == len(matches)
        chronology = []
        for match in matches:
            fixture = fixtures[match["fixture_external_id"]]
            assert fixture["season"] == season
            assert fixture["participant_kind"] == body["model"]["participant_kind"]
            assert fixture["status"] == match["status"] and match["status"] in ("FT", "AET", "PEN")
            played_at = datetime.fromisoformat(match["played_at"].replace("Z", "+00:00"))
            assert fixture["played_at"] == played_at <= as_of
            chronology.append((played_at, fixture["id"]))
            assert team["id"] in (fixture["home_team_id"], fixture["away_team_id"])
            home = fixture["home_team_id"] == team["id"]
            assert match["is_home"] == home
            gf = fixture["home_goals"] if home else fixture["away_goals"]
            ga = fixture["away_goals"] if home else fixture["home_goals"]
            assert (match["goals_for"], match["goals_against"]) == (gf, ga)
            expected = None
            if gf is not None and ga is not None:
                expected = "W" if gf > ga else "L" if gf < ga else None if match["status"] == "PEN" else "D"
            assert match["outcome"] == expected
        assert chronology == sorted(chronology), "Form must be oldest first"
        candidates = [p for p in data.players if p.team_id == team["id"] and p.season == season
                      and p.individual_points is not None and p.scored_minutes > 0 and p.scored_appearances > 0]
        expected_player = min(candidates, key=lambda p: (-p.individual_points, p.player_id), default=None)
        featured = team["featured_player"]
        if expected_player is None:
            assert featured is None, "No historical featured-player fallback"
        else:
            assert featured == {
                "id": expected_player.player_id, "name": expected_player.name,
                "photo_url": expected_player.photo_url, "individual_points": expected_player.individual_points,
                "appearances": expected_player.scored_appearances, "season": season,
            }, "Featured player must maximize current-season team-attributed total, not SFA/90"


async def main(
    response_json: str | None = None, max_response_seconds: float = 30.0, max_enrichment_seconds: float = 5.0,
):
    statements = []
    query_timings = []

    def record_statement(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.split()[0].upper())
        context._sfa_readonly_started = perf_counter()

    def record_timing(conn, cursor, statement, parameters, context, executemany):
        query_timings.append({
            "kind": "recent_results" if "recent_result_sides" in statement else "other",
            "elapsed_seconds": perf_counter() - context._sfa_readonly_started,
        })

    def check_performance(before, elapsed):
        timings = query_timings[before:]
        assert len(timings) == 5, f"Expected four aggregate reads plus one page form read, got {len(timings)}"
        enrichment = [t for t in timings if t["kind"] == "recent_results"]
        assert len(enrichment) == 1, "Exactly one page-bounded form query is required"
        assert elapsed <= max_response_seconds, f"Response exceeded {max_response_seconds}s: {elapsed:.3f}s"
        enrichment_elapsed = enrichment[0]["elapsed_seconds"]
        assert enrichment_elapsed <= max_enrichment_seconds, (
            f"Page form read exceeded {max_enrichment_seconds}s: {enrichment_elapsed:.3f}s"
        )
        return round(enrichment_elapsed, 3)

    event.listen(engine.sync_engine, "before_cursor_execute", record_statement)
    event.listen(engine.sync_engine, "after_cursor_execute", record_timing)
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await session.execute(text("SET TRANSACTION READ ONLY"))
                await session.execute(text("SET LOCAL statement_timeout = '30s'"))
                await session.execute(text("SET LOCAL plan_cache_mode = force_generic_plan"))
                assert await session.scalar(text("SHOW transaction_read_only")) == "on"

                async def readonly_db():
                    yield session

                app.dependency_overrides[get_db] = readonly_db
                # ASGITransport does not run lifespan (which would create schema).
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://staged") as client:
                    start = perf_counter()
                    before = len(statements)
                    response = await client.get("/api/v1/teams/ranking?scope=season-2026&page=1&limit=20")
                    elapsed = perf_counter() - start
                    assert response.status_code == 200, f"Unexpected status: {response.status_code}"
                    body = response.json()
                    assert body["total"] > 0 and body["ranking"], "Real population must not be empty"
                    assert body["model"]["experimental"] and not body["model"]["feeds_m1"]
                    assert any(r["elo_raw"] is not None for r in body["ranking"]), "Missing real ELO inputs"
                    assert any(r["squad_score"] is not None for r in body["ranking"]), "Missing real squad inputs"
                    for row in body["ranking"]:
                        assert row["availability"] is None
                        assert row["coverage"] is None or 0 <= row["coverage"] <= 1
                        assert row["score"] is None or 0 <= row["score"] <= 100
                    public_queries = len(statements) - before
                    assert public_queries == 5, (
                        f"Expected four aggregate reads plus one page form read, got {public_queries}"
                    )
                    enrichment_elapsed = check_performance(before, elapsed)
                    await verify_enrichment(session, body)

                    before = len(statements)
                    start = perf_counter()
                    second = (await client.get(
                        "/api/v1/teams/ranking?scope=season-2026&page=2&limit=20"
                    )).json()
                    second_elapsed = perf_counter() - start
                    second_enrichment_elapsed = check_performance(before, second_elapsed)
                    assert second["total"] == body["total"]
                    assert not {r["id"] for r in body["ranking"]}.intersection(r["id"] for r in second["ranking"])
                    first = body["ranking"][0]
                    filtered_response = await client.get("/api/v1/teams/ranking", params={
                        "season": "2026", "name": first["name"], "limit": 50,
                    })
                    filtered = filtered_response.json()
                    same = next(r for r in filtered["ranking"] if r["id"] == first["id"])
                    assert same["score"] == first["score"], "Filtering must not alter population normalization"
                    assert same["featured_player"] == first["featured_player"]
                    assert same["recent_results"] == first["recent_results"]
                    before = len(statements)
                    overrun = (await client.get("/api/v1/teams/ranking", params={
                        "season": "2026", "page": body["pagination"]["total_pages"] + 1, "limit": 20,
                    })).json()
                    assert overrun["ranking"] == [] and overrun["total"] == body["total"]
                    assert len(statements) - before == 4, "Empty pages must skip the form read"
                    invalid = await client.get("/api/v1/teams/ranking?season=2026&scope=season-2026")
                    assert invalid.status_code == 422
                    domestic_display = {}
                    for club, league in (("Barcelona", "La Liga"), ("Liverpool", "Premier League"),
                                         ("Paris Saint Germain", "Ligue 1")):
                        club_body = (await client.get("/api/v1/teams/ranking", params={
                            "season": "2026", "name": club, "limit": 50,
                        })).json()
                        club_row = next(r for r in club_body["ranking"] if r["name"] == club)
                        assert club_row["competition"] == league, f"Wrong domestic league for {club}"
                        assert club_body["model"]["rules_version_id"] == body["model"]["rules_version_id"]
                        assert club_body["model"]["population_teams"] == body["model"]["population_teams"]
                        domestic_display[club] = league
                    national = (await client.get(
                        "/api/v1/teams/ranking?season=2026&participant_kind=national&limit=20"
                    )).json()
                    canonical = (await client.get(
                        "/api/v1/teams/ranking?season=2026&participant_kind=national_team&limit=20"
                    )).json()
                    assert national["total"] > 0 and national["ranking"] == canonical["ranking"]
                    assert national["model"]["participant_kind"] == "national_team"
                    await verify_enrichment(session, national)
                    assert set(statements) <= {"SELECT", "WITH", "SET", "SHOW"}, "Only read-only SQL is permitted"
                    if response_json:
                        Path(response_json).write_text(json.dumps(body, indent=2), encoding="utf-8")
                    print(json.dumps({
                        "status": "passed", "read_only": True, "scope": body["scope"],
                        "plan_cache_mode": "force_generic_plan",
                        "elapsed_seconds": round(elapsed, 3), "aggregate_queries": public_queries,
                        "enrichment_queries": 1, "enrichment_elapsed_seconds": enrichment_elapsed,
                        "second_page_elapsed_seconds": round(second_elapsed, 3),
                        "second_page_enrichment_elapsed_seconds": second_enrichment_elapsed,
                        "max_response_seconds": max_response_seconds,
                        "max_enrichment_seconds": max_enrichment_seconds,
                        "fixture_json": response_json,
                        "total_teams": body["total"], "rules_version_id": body["model"]["rules_version_id"],
                        "data_cutoff": body["model"]["data_cutoff"],
                        "domestic_display": domestic_display, "national_teams": national["total"],
                        "page_observed_players": sum(r["observed_players"] for r in body["ranking"]),
                        "page_scored_players": sum(r["scored_players"] for r in body["ranking"]),
                        "top_teams": [{k: r[k] for k in (
                            "id", "name", "score", "elo_raw", "squad_score", "coverage",
                            "elo_season", "squad_season", "squad_data_cutoff",
                        )} for r in body["ranking"][:5]],
                        "checks": ["nonempty_real_elo_and_squad", "stable_filters", "disjoint_pages", "validation_422",
                                   "domestic_display", "national_aliases", "page_bounded_form", "actual_scores",
                                   "chronological_last5", "unknown_missing_and_level_pen", "current_season_featured",
                                   "max_team_individual_total", "empty_page_skips_enrichment", "latency_budgets"],
                    }, indent=2))
    finally:
        app.dependency_overrides.pop(get_db, None)
        event.remove(engine.sync_engine, "before_cursor_execute", record_statement)
        event.remove(engine.sync_engine, "after_cursor_execute", record_timing)
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--response-json", "--fixture-json", dest="response_json",
                        help="Optional path for the public API response fixture (includes enrichment)")
    parser.add_argument("--max-response-seconds", type=float, default=30.0)
    parser.add_argument("--max-enrichment-seconds", type=float, default=5.0)
    args = parser.parse_args()
    if args.max_response_seconds <= 0 or args.max_enrichment_seconds <= 0:
        parser.error("Performance budgets must be positive")
    asyncio.run(main(args.response_json, args.max_response_seconds, args.max_enrichment_seconds))
