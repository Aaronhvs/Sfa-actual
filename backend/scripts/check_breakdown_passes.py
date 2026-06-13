"""
Verifica si passes_completed aparece en el breakdown de sfa_season_scores
para jugadores específicos — confirma si el scoring nuevo se aplicó o no.
"""
import asyncio
from sqlalchemy import text
from sfa.infrastructure.database import AsyncSessionLocal


PLAYERS = [
    ("Pedri",          "pedri"),
    ("Bruno Fernandes", "fernand"),
    ("Angelo Stiller", "stiller"),
    ("Lamine Yamal",   "yamal"),
    ("Joshua Kimmich", "kimmich"),
]


async def main():
    async with AsyncSessionLocal() as s:

        print("=" * 72)
        print("BREAKDOWN EN sfa_season_scores (últimos scores guardados)")
        print("=" * 72)

        for display, search in PLAYERS:
            r = await s.execute(text("""
                SELECT
                    p.name,
                    c.name                      AS competition,
                    s.total_pts,
                    s.matches_played,
                    s.last_updated,
                    s.breakdown->>'passes_completed'   AS pc_json,
                    s.breakdown->>'goal'               AS goal_json,
                    s.breakdown->>'assist'             AS assist_json,
                    s.breakdown->>'stats'              AS stats_json
                FROM sfa_season_scores s
                JOIN players p      ON s.player_id      = p.id
                JOIN competitions c ON s.competition_id = c.id
                WHERE p.name ILIKE :name
                  AND s.season = '2024'
                ORDER BY s.total_pts DESC
            """), {"name": f"%{search}%"})
            rows = r.fetchall()

            if not rows:
                print(f"\n[{display}] → NO ENCONTRADO")
                continue

            player_name = rows[0][0]
            print(f"\n{'─'*72}")
            print(f"  {player_name}")
            print(f"  {'Liga':<25} {'Pts':>9} {'Partidos':>9} {'Actualizado':<22} {'passes_completed'}")
            print(f"  {'-'*70}")

            for name, comp, pts, matches, updated, pc, goal, assist, stats in rows:
                has_pc   = "✓ SÍ" if pc else "✗ NO"
                pc_pts   = pc if pc else "—"
                print(f"  {comp:<25} {round(pts):>9} {matches:>9} {str(updated)[:19]:<22} {has_pc}  ({pc_pts})")

        # ── Resumen global: ¿cuántos jugadores tienen passes_completed en su breakdown?
        print(f"\n\n{'='*72}")
        print("RESUMEN: jugadores con/sin passes_completed en su breakdown")
        print("=" * 72)

        r2 = await s.execute(text("""
            SELECT
                c.name                                                          AS competition,
                COUNT(*)                                                        AS total_jugadores,
                SUM(CASE WHEN s.breakdown ? 'passes_completed' THEN 1 ELSE 0 END) AS con_pc,
                SUM(CASE WHEN NOT (s.breakdown ? 'passes_completed') THEN 1 ELSE 0 END) AS sin_pc,
                MAX(s.last_updated)                                             AS ultima_actualizacion
            FROM sfa_season_scores s
            JOIN competitions c ON s.competition_id = c.id
            WHERE s.season = '2024'
            GROUP BY c.name
            ORDER BY ultima_actualizacion DESC
        """))
        rows2 = r2.fetchall()

        print(f"\n  {'Liga':<25} {'Total':>7} {'Con PC':>7} {'Sin PC':>7} {'Última actualización'}")
        print(f"  {'-'*72}")
        for comp, total, con, sin, updated in rows2:
            marker = " ← DESACTUALIZADA" if sin > 0 else ""
            print(f"  {comp:<25} {total:>7} {con:>7} {sin:>7}  {str(updated)[:19]}{marker}")


asyncio.run(main())
