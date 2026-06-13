"""
Diagnóstico: verifica si passes_accuracy llega de la API o queda en 0.
Busca a Pedri y Stiller en la DB y compara la cobertura de accuracy por liga.
"""
import asyncio
from sqlalchemy import text
from sfa.infrastructure.database import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as s:

        # ── 1. Jugadores específicos ────────────────────────────────────────
        PLAYERS = [
            ("Pedri",          "pedri"),
            ("Angelo Stiller", "stiller"),
            ("Bruno Fernand",  "fernand"),
            ("Lamine Yamal",   "yamal"),
        ]

        print("=" * 70)
        print("PASSES_ACCURACY Y PASSES_TOTAL POR PARTIDO (primeros 5 partidos)")
        print("=" * 70)

        for display, search in PLAYERS:
            r = await s.execute(text("""
                SELECT
                    p.name,
                    f.played_at::date,
                    c.name              AS competition,
                    ps.passes_total,
                    ps.passes_accuracy,
                    ps.minutes,
                    CASE
                        WHEN ps.passes_accuracy = 0 AND ps.passes_total > 0
                        THEN 'ACCURACY_NULL'
                        WHEN ps.passes_accuracy = 0 AND ps.passes_total = 0
                        THEN 'SIN_DATOS'
                        ELSE 'OK'
                    END                 AS estado
                FROM player_stats ps
                JOIN players p     ON ps.player_id  = p.id
                JOIN fixtures f    ON ps.fixture_id = f.id
                JOIN competitions c ON f.competition_id = c.id
                WHERE p.name ILIKE :name
                  AND f.season = '2024'
                ORDER BY f.played_at
                LIMIT 8
            """), {"name": f"%{search}%"})
            rows = r.fetchall()
            if not rows:
                print(f"\n[{display}] → NO ENCONTRADO EN DB")
                continue
            print(f"\n[{rows[0][0]}]")
            print(f"  {'Fecha':<12} {'Liga':<22} {'Total':>6} {'Acc%':>5} {'Mins':>5} {'Estado'}")
            print(f"  {'-'*65}")
            for row in rows:
                _, fecha, comp, total, acc, mins, estado = row
                print(f"  {str(fecha):<12} {comp:<22} {total:>6} {acc:>5} {mins:>5}  {estado}")

        # ── 2. Cobertura global de accuracy por competición ─────────────────
        print("\n\n" + "=" * 70)
        print("COBERTURA DE PASSES_ACCURACY POR COMPETICIÓN")
        print("(partidos donde passes_total > 0)")
        print("=" * 70)

        r2 = await s.execute(text("""
            SELECT
                c.name                                                          AS competition,
                COUNT(*)                                                        AS total_registros,
                SUM(CASE WHEN ps.passes_accuracy > 0 THEN 1 ELSE 0 END)        AS con_accuracy,
                SUM(CASE WHEN ps.passes_accuracy = 0
                          AND ps.passes_total > 0 THEN 1 ELSE 0 END)           AS sin_accuracy,
                ROUND(
                    100.0 * SUM(CASE WHEN ps.passes_accuracy > 0 THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(*), 0), 1
                )                                                               AS pct_cobertura
            FROM player_stats ps
            JOIN fixtures f      ON ps.fixture_id    = f.id
            JOIN competitions c  ON f.competition_id = c.id
            WHERE ps.passes_total > 0
              AND f.season = '2024'
            GROUP BY c.name
            ORDER BY pct_cobertura DESC NULLS LAST
        """))
        rows2 = r2.fetchall()
        print(f"\n  {'Liga':<25} {'Total':>7} {'Con acc':>8} {'Sin acc':>8} {'%':>6}")
        print(f"  {'-'*58}")
        for comp, total, con, sin, pct in rows2:
            pct_str = f"{pct}%" if pct is not None else "N/A"
            print(f"  {comp:<25} {total:>7} {con:>8} {sin:>8} {pct_str:>6}")

        # ── 3. Top 10 jugadores con más pts y sus passes en DB ──────────────
        print("\n\n" + "=" * 70)
        print("TOP 10 EN RANKING — ¿TIENEN PASSES_ACCURACY EN DB?")
        print("=" * 70)

        r3 = await s.execute(text("""
            SELECT
                p.name,
                p.position,
                SUM(s.total_pts)                                                AS total_pts,
                ROUND(AVG(ps.passes_total))                                     AS avg_passes_total,
                ROUND(AVG(ps.passes_accuracy))                                  AS avg_passes_acc,
                SUM(CASE WHEN ps.passes_accuracy > 0 THEN 1 ELSE 0 END)        AS fixtures_con_acc,
                COUNT(ps.id)                                                    AS fixtures_total
            FROM sfa_season_scores s
            JOIN players p       ON s.player_id      = p.id
            JOIN player_stats ps ON ps.player_id     = p.id
            JOIN fixtures f      ON ps.fixture_id    = f.id
            WHERE s.season = '2024'
              AND f.season  = '2024'
            GROUP BY p.id, p.name, p.position
            ORDER BY total_pts DESC
            LIMIT 10
        """))
        rows3 = r3.fetchall()
        print(f"\n  {'Jugador':<22} {'Pos':>4} {'Pts':>9} {'AvgPases':>9} {'AvgAcc':>7} {'ConAcc':>7} {'TotalF':>7}")
        print(f"  {'-'*72}")
        for name, pos, pts, avg_p, avg_a, con_acc, tot_f in rows3:
            print(f"  {name:<22} {str(pos):>4} {round(pts):>9} {int(avg_p or 0):>9} {int(avg_a or 0):>7}% {int(con_acc):>7} {int(tot_f):>7}")


asyncio.run(main())
