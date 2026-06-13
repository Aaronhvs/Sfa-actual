"""
Debug ingestion de Copa del Rey: traza qué fixtures se procesan y por qué
la final no entra en el acumulado de Yamal
"""
import asyncio
import logging

from sfa.application.use_cases.ingest_competition import LEAGUES, _PlayerAccum, _parse_matchday
from sfa.core.config import get_settings
from sfa.infrastructure.database import AsyncSessionLocal
from sfa.infrastructure.providers.api_football import APIFootballProvider
from sfa.infrastructure.repositories.ingestion_repository import IngestionRepository

logging.basicConfig(level=logging.WARNING)


async def main():
    settings = get_settings()
    provider = APIFootballProvider(
        api_key=settings.API_FOOTBALL_KEY,
        base_url=settings.API_FOOTBALL_BASE_URL,
    )

    copa_config = next(l for l in LEAGUES if l.id == 143)

    async with AsyncSessionLocal() as session:
        repo = IngestionRepository(session)

        # 1. Get standings
        standings = await provider.fetch_standings(140, 2024)
        print(f"Standings: {len(standings)} equipos")

        competition_id = await repo.upsert_competition(
            copa_config.name, copa_config.country, copa_config.comp_factor
        )
        print(f"Copa del Rey competition_id={competition_id}")

        team_id_map = {}
        pos_cache = {}
        for standing in standings:
            db_id = await repo.upsert_team(standing.team_external_id, standing.team_name, competition_id)
            team_id_map[standing.team_external_id] = db_id
            pos_cache[standing.team_external_id] = standing.position

        top_teams = sorted(standings, key=lambda s: s.position)[:copa_config.top_n]
        print(f"\nTop {copa_config.top_n} teams: {[s.team_name for s in top_teams]}")

        processed_fixture_ids: set[int] = set()
        player_accum: dict[int, _PlayerAccum] = {}

        for team_standing in top_teams:
            team_ext_id = team_standing.team_external_id
            fixtures = await provider.fetch_team_fixtures(team_ext_id, 143, 2024)
            print(f"\n{team_standing.team_name} (ext={team_ext_id}): {len(fixtures)} fixtures")

            for fixture in fixtures:
                if fixture.external_id in processed_fixture_ids:
                    print(f"  [{fixture.round_str}] ext={fixture.external_id} SKIP (already processed)")
                    continue
                processed_fixture_ids.add(fixture.external_id)

                # Ensure teams
                for ext_id, name in [
                    (fixture.home_team_external_id, fixture.home_team_name),
                    (fixture.away_team_external_id, fixture.away_team_name),
                ]:
                    if ext_id not in team_id_map:
                        db_id = await repo.upsert_team(ext_id, name, competition_id)
                        team_id_map[ext_id] = db_id
                        if ext_id not in pos_cache:
                            pos_cache[ext_id] = 10

                home_db_id = team_id_map[fixture.home_team_external_id]
                away_db_id = team_id_map[fixture.away_team_external_id]
                stage = provider.get_stage(fixture.round_str, fixture.league_name)
                matchday_num = _parse_matchday(fixture.round_str)

                fixture_db_id = await repo.upsert_fixture(
                    fixture.external_id, competition_id,
                    home_db_id, away_db_id,
                    stage, "2024", fixture.played_at, matchday_num,
                )
                print(f"  [{fixture.round_str}] ext={fixture.external_id} -> db_id={fixture_db_id}")

                for proc_team_ext_id in (
                    fixture.home_team_external_id,
                    fixture.away_team_external_id,
                ):
                    player_stats_list = await provider.fetch_fixture_players(
                        fixture.external_id, proc_team_ext_id
                    )

                    yamal_stats = [ps for ps in player_stats_list if "Yamal" in ps.player_name]
                    if yamal_stats:
                        ps = yamal_stats[0]
                        print(f"    YAMAL: mins={ps.minutes}, goals={ps.goals}, assists={ps.assists}")

                        player_db_id = await repo.upsert_player(
                            ps.player_external_id, ps.player_name, team_id_map[proc_team_ext_id], None
                        )
                        if player_db_id not in player_accum:
                            player_accum[player_db_id] = _PlayerAccum()
                        accum = player_accum[player_db_id]
                        accum.matches_played += 1
                        accum.total_minutes += ps.minutes
                        print(f"    Acum: matches={accum.matches_played}, mins={accum.total_minutes}")

        print(f"\nFixtures únicos procesados: {len(processed_fixture_ids)}")
        print(f"1367758 en processed: {1367758 in processed_fixture_ids}")

        await session.rollback()  # Don't commit — solo debug


asyncio.run(main())
