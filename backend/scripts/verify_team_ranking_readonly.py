"""Exercise staged API code against real data in an enforced read-only transaction."""

import argparse
import asyncio
import json
from pathlib import Path
from time import perf_counter

from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text

from sfa.core.dependencies import get_db
from sfa.infrastructure.database import AsyncSessionLocal, engine
from sfa.main import app


async def main(response_json: str | None = None):
    statements = []

    def record_statement(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.split()[0].upper())

    event.listen(engine.sync_engine, "before_cursor_execute", record_statement)
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
                    assert public_queries == 4, f"Expected aggregate reads, got {public_queries}"

                    second = (await client.get(
                        "/api/v1/teams/ranking?scope=season-2026&page=2&limit=20"
                    )).json()
                    assert second["total"] == body["total"]
                    assert not {r["id"] for r in body["ranking"]}.intersection(r["id"] for r in second["ranking"])
                    first = body["ranking"][0]
                    filtered_response = await client.get("/api/v1/teams/ranking", params={
                        "season": "2026", "name": first["name"], "limit": 50,
                    })
                    filtered = filtered_response.json()
                    same = next(r for r in filtered["ranking"] if r["id"] == first["id"])
                    assert same["score"] == first["score"], "Filtering must not alter population normalization"
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
                    if response_json:
                        Path(response_json).write_text(json.dumps(body, indent=2), encoding="utf-8")
                    print(json.dumps({
                        "status": "passed", "read_only": True, "scope": body["scope"],
                        "plan_cache_mode": "force_generic_plan",
                        "elapsed_seconds": round(elapsed, 3), "aggregate_queries": public_queries,
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
                                   "domestic_display", "national_aliases"],
                    }, indent=2))
    finally:
        app.dependency_overrides.pop(get_db, None)
        event.remove(engine.sync_engine, "before_cursor_execute", record_statement)
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--response-json", help="Optional path for the public API response fixture")
    asyncio.run(main(parser.parse_args().response_json))
