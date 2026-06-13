import asyncio
from sqlalchemy import select, text
from sfa.infrastructure.database import AsyncSessionLocal
from sfa.infrastructure.models.fixtures.models import Fixture


async def check():
    async with AsyncSessionLocal() as s:
        # external_id del fixture 321 (Barca vs Brest)
        f321 = (await s.execute(select(Fixture.external_id).where(Fixture.id == 321))).scalar_one()
        print("Fixture 321 external_id:", f321)

        # external_id del fixture 329 (Barcelona vs Inter, semi leg1)
        f329 = (await s.execute(select(Fixture.external_id).where(Fixture.id == 329))).scalar_one()
        print("Fixture 329 (semi leg1) external_id:", f329)

        # Barcelona fixtures en CL con sus external_ids - todos los semis
        semis = (await s.execute(text(
            "SELECT f.id, f.external_id, f.played_at, f.stage, ht.name as home, at.name as away "
            "FROM fixtures f "
            "JOIN competitions c ON f.competition_id = c.id "
            "JOIN teams ht ON f.home_team_id = ht.id "
            "JOIN teams at ON f.away_team_id = at.id "
            "WHERE c.name ILIKE '%champion%' "
            "AND f.season = '2024' "
            "AND f.stage = 'semi' "
            "ORDER BY f.played_at"
        ))).all()
        print("\nSemi-finales CL en DB:")
        for r in semis:
            print(" ", r)


asyncio.run(check())
