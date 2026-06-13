"""Prueba fetch_team_fixtures para Copa del Rey 2024 - Barcelona"""
import asyncio
from sfa.core.config import get_settings
from sfa.infrastructure.providers.api_football import APIFootballProvider


async def main():
    settings = get_settings()
    provider = APIFootballProvider(
        api_key=settings.API_FOOTBALL_KEY,
        base_url=settings.API_FOOTBALL_BASE_URL,
    )

    print(f"API key: {settings.API_FOOTBALL_KEY[:8]}...")
    print(f"Base URL: {settings.API_FOOTBALL_BASE_URL}")

    # Barcelona en Copa del Rey
    fixtures = await provider.fetch_team_fixtures(529, 143, 2024)
    print(f"\nFixtures Barcelona en Copa del Rey: {len(fixtures)}")
    for f in sorted(fixtures, key=lambda x: x.played_at):
        print(f"  ext={f.external_id} | {f.played_at.date()} | {f.round_str}")

    # Real Madrid en Copa del Rey
    fixtures2 = await provider.fetch_team_fixtures(541, 143, 2024)
    print(f"\nFixtures Real Madrid en Copa del Rey: {len(fixtures2)}")
    for f in sorted(fixtures2, key=lambda x: x.played_at):
        print(f"  ext={f.external_id} | {f.played_at.date()} | {f.round_str}")


asyncio.run(main())
