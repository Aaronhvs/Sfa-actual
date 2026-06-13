"""
Diagnóstico de integridad de competitions y sfa_season_scores.
Detecta duplicados y muestra el top 5 real del ranking con competition_ids.
"""
import asyncio
from sqlalchemy import text
from sfa.infrastructure.database import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as s:

        # ── 1. Todas las competiciones en la DB ─────────────────────────────
        print("=" * 60)
        print("COMPETICIONES EN DB (id, name, country)")
        print("=" * 60)
        r = await s.execute(text("""
            SELECT id, name, country, competition_factor
            FROM competitions
            ORDER BY id
        """))
        comps = r.fetchall()
        for cid, name, country, factor in comps:
            print(f"  id={cid:>3}  [{country}]  {name}  (factor={factor})")

        # ── 2. ¿Hay nombres duplicados? ──────────────────────────────────────
        print("\n" + "=" * 60)
        print("NOMBRES DUPLICADOS EN competitions")
        print("=" * 60)
        r2 = await s.execute(text("""
            SELECT name, COUNT(*) as cnt, array_agg(id ORDER BY id) as ids
            FROM competitions
            GROUP BY name
            HAVING COUNT(*) > 1
        """))
        dups = r2.fetchall()
        if not dups:
            print("  Ninguno — los nombres son únicos.")
        else:
            for name, cnt, ids in dups:
                print(f"  DUPLICADO: '{name}'  ({cnt} filas)  ids={ids}")

        # ── 3. Top 10 real del ranking con competition_ids ───────────────────
        print("\n" + "=" * 60)
        print("TOP 10 RANKING — player_id + competition_ids + pts reales")
        print("=" * 60)
        r3 = await s.execute(text("""
            SELECT
                p.id            AS player_id,
                p.name,
                p.position,
                SUM(s.total_pts)                                    AS total_pts,
                COUNT(s.id)                                         AS num_filas,
                array_agg(s.competition_id ORDER BY s.total_pts DESC) AS comp_ids,
                array_agg(s.total_pts::int ORDER BY s.total_pts DESC) AS pts_por_comp
            FROM sfa_season_scores s
            JOIN players p ON s.player_id = p.id
            WHERE s.season = '2024'
            GROUP BY p.id, p.name, p.position
            ORDER BY total_pts DESC
            LIMIT 10
        """))
        rows3 = r3.fetchall()
        print(f"\n  {'ID':>5} {'Jugador':<22} {'Pos':>4} {'Total':>9} {'Filas':>6}  Comp IDs (pts)")
        print(f"  {'-'*75}")
        for pid, name, pos, pts, nfilas, comp_ids, pts_comp in rows3:
            detail = "  ".join(f"c{cid}={p}" for cid, p in zip(comp_ids, pts_comp))
            print(f"  {pid:>5} {name:<22} {str(pos):>4} {round(pts):>9} {nfilas:>6}  {detail}")

        # ── 4. sfa_season_scores con competition_id que no existen ──────────
        print("\n" + "=" * 60)
        print("ORPHAN SCORES (competition_id sin fila en competitions)")
        print("=" * 60)
        r4 = await s.execute(text("""
            SELECT DISTINCT s.competition_id, COUNT(*) as filas
            FROM sfa_season_scores s
            LEFT JOIN competitions c ON s.competition_id = c.id
            WHERE c.id IS NULL
            GROUP BY s.competition_id
        """))
        orphans = r4.fetchall()
        if not orphans:
            print("  Ninguno — todos los competition_ids tienen registro.")
        else:
            for cid, cnt in orphans:
                print(f"  ORPHAN competition_id={cid}  ({cnt} filas en sfa_season_scores)")


asyncio.run(main())
