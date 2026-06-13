import asyncio
from sfa.infrastructure.database import AsyncSessionLocal
from sqlalchemy import text


async def main():
    async with AsyncSessionLocal() as s:
        r = await s.execute(text("""
            SELECT f.id, f.external_id, f.stage, f.played_at::date, ht.name, at.name
            FROM fixtures f
            JOIN teams ht ON f.home_team_id=ht.id
            JOIN teams at ON f.away_team_id=at.id
            WHERE f.competition_id=22 AND f.season='2024'
            ORDER BY f.played_at
        """))
        rows = r.fetchall()
        print(f"Total Copa del Rey fixtures en DB: {len(rows)}")
        for row in rows:
            print(f"  id={row[0]}, ext={row[1]}, stage={row[2]}, date={row[3]}, {row[4]} vs {row[5]}")

        r2 = await s.execute(text("SELECT id, external_id, competition_id FROM fixtures WHERE external_id=1367758"))
        row2 = r2.fetchone()
        if row2:
            print(f"\nFinal encontrada: db_id={row2[0]}, ext={row2[1]}, comp_id={row2[2]}")
        else:
            print("\nFinal (ext_id=1367758) NO está en la tabla fixtures")


asyncio.run(main())
