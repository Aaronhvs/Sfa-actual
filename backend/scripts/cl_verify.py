import asyncio
from sqlalchemy import text
from sfa.infrastructure.database import AsyncSessionLocal


async def check():
    async with AsyncSessionLocal() as s:
        # Semis en DB
        r = await s.execute(text(
            "SELECT f.id, f.external_id, f.played_at, f.stage, ht.name as home, at.name as away "
            "FROM fixtures f "
            "JOIN teams ht ON f.home_team_id = ht.id "
            "JOIN teams at ON f.away_team_id = at.id "
            "JOIN competitions c ON f.competition_id = c.id "
            "WHERE c.name ILIKE '%champion%' AND f.season='2024' AND f.stage='semi' ORDER BY f.played_at"
        ))
        print("=== Semis en DB ===")
        for row in r:
            print(row)

        # PlayerStats Yamal CL
        r2 = await s.execute(text(
            "SELECT ps.fixture_id, ps.minutes, ps.goals, f.played_at, f.stage "
            "FROM player_stats ps "
            "JOIN fixtures f ON ps.fixture_id = f.id "
            "JOIN competitions c ON f.competition_id = c.id "
            "WHERE ps.player_id = 34 AND c.name ILIKE '%champion%' ORDER BY f.played_at"
        ))
        rows = list(r2)
        print(f"\n=== PlayerStats Yamal en CL: {len(rows)} fixtures ===")
        for row in rows:
            print(row)

        # Verificar perfil completo via API
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:8000/api/v1/players/34?season=2024")
            d = resp.json()
            print(f"\n=== Perfil Yamal via API ===")
            print(f"matches: {d.get('matches')} | goals: {d.get('total_goals')} | assists: {d.get('total_assists')} | sfa_pts: {d.get('sfa_pts')} | rank: {d.get('global_rank')}")
            print(f"competitions: {d.get('competitions')}")


asyncio.run(check())
