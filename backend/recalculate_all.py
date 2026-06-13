"""Recalculate SFA scores for all competitions after scoring changes."""
import asyncio
import logging

logging.basicConfig(level=logging.WARNING, format="%(message)s")

from sfa.application.use_cases.recalculate_scores import RecalculateScoresUseCase
from sfa.infrastructure.database import AsyncSessionLocal
from sfa.infrastructure.repositories.enrichment_repository import EnrichmentRepository

COMPETITIONS = [1, 3, 6, 7, 9, 10, 22, 23, 90, 92, 94, 96]
NAMES = {
    1: "La Liga", 3: "Premier League", 6: "Bundesliga", 7: "Serie A",
    9: "Ligue 1", 10: "Champions League", 22: "Copa del Rey",
    23: "Supercopa", 90: "FA Cup", 92: "DFB-Pokal",
    94: "Coppa Italia", 96: "Coupe de France",
}
SEASON = "2024"


async def run() -> None:
    for comp_id in COMPETITIONS:
        async with AsyncSessionLocal() as session:
            repo = EnrichmentRepository(session)
            use_case = RecalculateScoresUseCase(repo)
            result = await use_case.execute(comp_id, SEASON)
            await session.commit()
        print(f"  {NAMES[comp_id]}: {result}")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(run())
