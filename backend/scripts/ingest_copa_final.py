"""
Script de ingesta directa para la Final de Copa del Rey 2024/25
Barcelona vs Real Madrid (ext_id=1367758, AET)
"""
import asyncio
import logging

from sfa.application.use_cases.ingest_competition import (
    LEAGUES,
    IngestCompetitionUseCase,
    LeagueConfig,
)
from sfa.core.config import get_settings
from sfa.domain.scoring.services import SFAScoringService
from sfa.infrastructure.database import AsyncSessionLocal
from sfa.infrastructure.providers.api_football import APIFootballProvider
from sfa.infrastructure.repositories.ingestion_repository import IngestionRepository

logging.basicConfig(level=logging.WARNING)

COPA_LEAGUE_ID = 143
SEASON = 2024

# Override top_n to ensure Real Madrid is covered too
copa_config = next(l for l in LEAGUES if l.id == COPA_LEAGUE_ID)


async def main() -> None:
    settings = get_settings()
    provider = APIFootballProvider(
        api_key=settings.API_FOOTBALL_KEY,
        base_url="https://v3.football.api-sports.io",
    )

    async with AsyncSessionLocal() as session:
        repo = IngestionRepository(session)
        scoring = SFAScoringService()

        use_case = IngestCompetitionUseCase(provider, repo, scoring)

        print(f"Iniciando ingesta: {copa_config.name} (season={SEASON}, top_n={copa_config.top_n})")
        result = await use_case.execute(copa_config, SEASON)
        await session.commit()
        print(f"Resultado: {result.status}, players={result.players_processed}, fixtures={result.fixtures_processed}")
        if result.error:
            print(f"Error: {result.error}")


asyncio.run(main())
