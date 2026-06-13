"""Run Understat xa enrichment directly (no Celery) for all 5 leagues."""
import asyncio
import sys
sys.path.insert(0, "/code/src")

from sfa.application.use_cases.enrich_with_understat import EnrichWithUnderstatUseCase
from sfa.application.use_cases.recalculate_scores import RecalculateScoresUseCase
from sfa.infrastructure.database import AsyncSessionLocal
from sfa.infrastructure.providers.understat_scraper import UnderstatScraper
from sfa.infrastructure.repositories.enrichment_repository import EnrichmentRepository

LEAGUES = [
    (1, "La Liga", 2024),
    (3, "Premier League", 2024),
    (6, "Bundesliga", 2024),
    (7, "Serie A", 2024),
    (9, "Ligue 1", 2024),
]
SEASON = "2024"


async def run_league(comp_id: int, comp_name: str, season_int: int) -> None:
    print(f"\n{'='*55}")
    print(f"[{comp_name}] Starting Understat enrichment...")
    scraper = UnderstatScraper()
    async with AsyncSessionLocal() as session:
        repo = EnrichmentRepository(session)
        use_case = EnrichWithUnderstatUseCase(scraper, repo)
        result = await use_case.execute(comp_name, comp_id, SEASON, season_int)
        await session.commit()
    print(f"[{comp_name}] enrichment: matched={result.players_matched} "
          f"skipped={result.players_skipped} stats_enriched={result.stats_enriched} "
          f"status={result.status}")

    print(f"[{comp_name}] Recalculating scores...")
    async with AsyncSessionLocal() as session:
        repo = EnrichmentRepository(session)
        use_case = RecalculateScoresUseCase(repo)
        result = await use_case.execute(comp_id, SEASON)
        await session.commit()
    print(f"[{comp_name}] recalc: events_updated={result.events_updated} "
          f"scores_updated={result.scores_updated}")


async def main() -> None:
    for comp_id, comp_name, season_int in LEAGUES:
        try:
            await run_league(comp_id, comp_name, season_int)
        except Exception as e:
            print(f"[{comp_name}] ERROR: {e}")

    # Summary
    print(f"\n{'='*55}")
    print("XA COVERAGE SUMMARY:")
    from sqlalchemy import text
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT c.name, COUNT(DISTINCT ps.player_id) as cnt
            FROM player_stats ps
            JOIN fixtures f ON f.id = ps.fixture_id
            JOIN competitions c ON c.id = f.competition_id
            WHERE ps.xa > 0
            GROUP BY c.name ORDER BY c.name
        """))
        rows = result.fetchall()
        if rows:
            for name, cnt in rows:
                print(f"  {name:<25} {cnt:>4} players with xa")
        else:
            print("  No xa data found!")


asyncio.run(main())
