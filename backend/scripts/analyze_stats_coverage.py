"""Coverage of all player_stats fields + scoring impact."""
import asyncio
import sys
sys.path.insert(0, "/code/src")

from sqlalchemy import text
from sfa.infrastructure.database import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as session:

        # Coverage of every scoreable field
        r = await session.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN passes_key > 0 THEN 1 ELSE 0 END) as has_key_passes,
                SUM(CASE WHEN dribbles_won > 0 THEN 1 ELSE 0 END) as has_dribbles,
                SUM(CASE WHEN duels_won > 0 THEN 1 ELSE 0 END) as has_duels,
                SUM(CASE WHEN tackles_won > 0 THEN 1 ELSE 0 END) as has_tackles,
                SUM(CASE WHEN interceptions > 0 THEN 1 ELSE 0 END) as has_interceptions,
                SUM(CASE WHEN blocks > 0 THEN 1 ELSE 0 END) as has_blocks,
                SUM(CASE WHEN shots_on > 0 THEN 1 ELSE 0 END) as has_shots,
                SUM(CASE WHEN fouls_drawn > 0 THEN 1 ELSE 0 END) as has_fouls,
                SUM(CASE WHEN clearances > 0 THEN 1 ELSE 0 END) as has_clearances,
                SUM(CASE WHEN recoveries_opp_half > 0 THEN 1 ELSE 0 END) as has_recoveries,
                SUM(CASE WHEN pressures_success > 0 THEN 1 ELSE 0 END) as has_pressures,
                SUM(CASE WHEN progressive_passes > 0 THEN 1 ELSE 0 END) as has_prog_p,
                SUM(CASE WHEN progressive_carries > 0 THEN 1 ELSE 0 END) as has_prog_c,
                SUM(CASE WHEN xg > 0 THEN 1 ELSE 0 END) as has_xg,
                SUM(CASE WHEN rating IS NOT NULL THEN 1 ELSE 0 END) as has_rating
            FROM player_stats
        """))
        row = r.fetchone()
        total = row[0]
        fields = [
            "passes_key", "dribbles_won", "duels_won", "tackles_won",
            "interceptions", "blocks", "shots_on", "fouls_drawn",
            "clearances", "recoveries_opp_half", "pressures_success",
            "prog_passes", "prog_carries", "xg", "rating"
        ]
        print("=== Field coverage (% of fixtures with value > 0) ===")
        for i, field in enumerate(fields):
            val = row[i + 1]
            pct = val / total * 100
            bar = "#" * int(pct / 5)
            print(f"  {field:22s}: {val:6d}/{total} ({pct:5.1f}%) {bar}")

        # Average values for fields with good coverage — MF only
        r = await session.execute(text("""
            SELECT
                ROUND(AVG(ps.passes_key), 2) as avg_key_p,
                ROUND(AVG(ps.dribbles_won), 2) as avg_dribs,
                ROUND(AVG(ps.duels_won), 2) as avg_duels,
                ROUND(AVG(ps.tackles_won), 2) as avg_tackles,
                ROUND(AVG(ps.interceptions), 2) as avg_ints,
                ROUND(AVG(ps.fouls_drawn), 2) as avg_fouls,
                ROUND(AVG(ps.shots_on), 2) as avg_shots,
                ROUND(AVG(ps.clearances), 2) as avg_clears,
                COUNT(*) as fixtures
            FROM player_stats ps
            JOIN players p ON p.id = ps.player_id
            WHERE p.position IN ('MC', 'MCO', 'MCD', 'MO', 'MI', 'MD')
        """))
        row = r.fetchone()
        print(f"\n=== MF averages per fixture (n={row[8]}) ===")
        print(f"  key_passes:    {row[0]}")
        print(f"  dribbles_won:  {row[1]}")
        print(f"  duels_won:     {row[2]}")
        print(f"  tackles_won:   {row[3]}")
        print(f"  interceptions: {row[4]}")
        print(f"  fouls_drawn:   {row[5]}")
        print(f"  shots_on:      {row[6]}")
        print(f"  clearances:    {row[7]}")

        # Top MF by current pts_per_fixture and their key stats
        r = await session.execute(text("""
            SELECT
                p.name,
                c.name as comp,
                COUNT(DISTINCT ps.fixture_id) as fixtures,
                ROUND(SUM(ss.total_pts) / NULLIF(ss.matches_played, 0), 1) as pts_per_match,
                ROUND(AVG(ps.passes_key), 1) as avg_key_p,
                ROUND(AVG(ps.dribbles_won), 1) as avg_dribs,
                ROUND(AVG(ps.fouls_drawn), 1) as avg_fouls
            FROM player_stats ps
            JOIN players p ON p.id = ps.player_id
            JOIN fixtures f ON f.id = ps.fixture_id
            JOIN competitions c ON c.id = f.competition_id
            JOIN sfa_season_scores ss ON ss.player_id = p.id
                AND ss.competition_id = f.competition_id
                AND ss.season = f.season
            WHERE p.position IN ('MC', 'MCO', 'MCD', 'MO', 'MI', 'MD')
              AND f.season = '2024'
            GROUP BY p.name, c.name, ss.total_pts, ss.matches_played
            ORDER BY pts_per_match DESC NULLS LAST
            LIMIT 15
        """))
        print("\n=== Top 15 MF by pts/match (2024) ===")
        for row in r.fetchall():
            print(f"  {row[0]:28s} ({row[2]:2d}fix) pts/m={row[3]:7.1f}  key_p={row[4]:4.1f} dribs={row[5]:4.1f} fouls={row[6]:4.1f}")


asyncio.run(main())
