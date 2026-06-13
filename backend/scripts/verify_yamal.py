import asyncio
import httpx


async def main():
    async with httpx.AsyncClient() as client:
        fixtures = (await client.get("http://localhost:8000/api/v1/players/34/fixtures?season=2024")).json()
        cl = [f for f in fixtures if "Champion" in f["competition"]]
        print(f"Fixtures CL de Yamal: {len(cl)}")
        for f in sorted(cl, key=lambda x: x["played_at"]):
            bd = f.get("breakdown") or {}
            shootout = bd.get("goal_shootout", {}).get("count", 0)
            goals = bd.get("goal", {}).get("count", 0)
            pens = bd.get("goal_penalty", {}).get("count", 0)
            assists = bd.get("assist", {}).get("count", 0)
            tag = ""
            if shootout:
                tag = f" [TANDA x{shootout}]"
            if goals:
                tag += f" [GOL x{goals}]"
            if pens:
                tag += f" [PEN x{pens}]"
            if assists:
                tag += f" [AST x{assists}]"
            date = f["played_at"][:10]
            stage = f["stage"]
            home = f["home_team"]
            away = f["away_team"]
            mins = f["minutes"]
            pts = round(f["sfa_pts"])
            print(f"  {date} | {stage:<12} | {home} vs {away} | mins={mins} | {pts}pts{tag}")


asyncio.run(main())
