"""
Migración 0010 — API-Football Complete Stats

Elimina 8 columnas con 0% cobertura (FBref/Understat-only) y añade 11 columnas
nuevas extraídas de fixtures/players de API-Football.

Uso:
    docker exec backend-api-1 python3 scripts/migrate_0010_player_stats.py
    docker exec backend-api-1 python3 scripts/migrate_0010_player_stats.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import text

sys.path.insert(0, "src")

from sfa.infrastructure.database import AsyncSessionLocal  # noqa: E402

DROP_COLUMNS = [
    "xg",
    "xa",
    "progressive_passes",
    "progressive_carries",
    "recoveries_opp_half",
    "pressures_success",
    "clearances",
    "clearances_goal_line",
]

DROP_CONSTRAINTS = [
    "ck_ps_xg",
    "ck_ps_xa",
    "ck_ps_progressive_passes",
    "ck_ps_progressive_carries",
    "ck_ps_recoveries_opp_half",
    "ck_ps_pressures_success",
    "ck_ps_clearances",
    "ck_ps_clearances_goal_line",
]

ADD_COLUMNS = [
    ("shots_total",    "SMALLINT NOT NULL DEFAULT 0"),
    ("passes_total",   "SMALLINT NOT NULL DEFAULT 0"),
    ("passes_accuracy", "SMALLINT NOT NULL DEFAULT 0"),
    ("dribbles_past",  "SMALLINT NOT NULL DEFAULT 0"),
    ("duels_total",    "SMALLINT NOT NULL DEFAULT 0"),
    ("fouls_committed", "SMALLINT NOT NULL DEFAULT 0"),
    ("cards_yellow",   "SMALLINT NOT NULL DEFAULT 0"),
    ("cards_red",      "SMALLINT NOT NULL DEFAULT 0"),
    ("penalty_won",    "SMALLINT NOT NULL DEFAULT 0"),
    ("saves",          "SMALLINT NOT NULL DEFAULT 0"),
    ("goals_conceded", "SMALLINT NOT NULL DEFAULT 0"),
]

ADD_CONSTRAINTS = [
    ("ck_ps_shots_total",    "shots_total >= 0"),
    ("ck_ps_passes_total",   "passes_total >= 0"),
    ("ck_ps_passes_accuracy", "passes_accuracy BETWEEN 0 AND 100"),
    ("ck_ps_dribbles_past",  "dribbles_past >= 0"),
    ("ck_ps_duels_total",    "duels_total >= 0"),
    ("ck_ps_fouls_committed", "fouls_committed >= 0"),
    ("ck_ps_cards_yellow",   "cards_yellow >= 0"),
    ("ck_ps_cards_red",      "cards_red >= 0"),
    ("ck_ps_penalty_won",    "penalty_won >= 0"),
    ("ck_ps_saves",          "saves >= 0"),
    ("ck_ps_goals_conceded", "goals_conceded >= 0"),
]


async def run(dry_run: bool) -> None:
    async with AsyncSessionLocal() as session:
        # Verificar columnas actuales
        result = await session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'player_stats' ORDER BY ordinal_position"
        ))
        existing = {row[0] for row in result.fetchall()}
        print(f"Columnas actuales en player_stats: {len(existing)}")

        stmts: list[str] = []

        # DROP constraints primero (antes de DROP columns)
        for constraint_name in DROP_CONSTRAINTS:
            stmts.append(
                f"ALTER TABLE player_stats DROP CONSTRAINT IF EXISTS {constraint_name}"
            )

        # DROP columnas muertas
        for col in DROP_COLUMNS:
            if col in existing:
                stmts.append(f"ALTER TABLE player_stats DROP COLUMN IF EXISTS {col}")
            else:
                print(f"  [SKIP] Columna '{col}' ya no existe.")

        # ADD columnas nuevas
        for col, definition in ADD_COLUMNS:
            if col not in existing:
                stmts.append(f"ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS {col} {definition}")
            else:
                print(f"  [SKIP] Columna '{col}' ya existe.")

        # ADD constraints nuevos
        for constraint_name, expression in ADD_CONSTRAINTS:
            stmts.append(
                f"ALTER TABLE player_stats ADD CONSTRAINT {constraint_name} "
                f"CHECK ({expression}) NOT VALID"
            )

        if dry_run:
            print("\n[DRY-RUN] Sentencias que se ejecutarían:\n")
            for stmt in stmts:
                print(f"  {stmt};")
            print("\nNo se hizo ningún cambio en la DB.")
            return

        print(f"\nEjecutando {len(stmts)} sentencias...")
        for stmt in stmts:
            print(f"  → {stmt[:80]}...")
            await session.execute(text(stmt))

        await session.commit()
        print("\n[OK] Migración 0010 aplicada correctamente.")

        # Verificar resultado
        result = await session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'player_stats' ORDER BY ordinal_position"
        ))
        final_cols = [row[0] for row in result.fetchall()]
        print(f"\nColumnas finales ({len(final_cols)}): {', '.join(final_cols)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migración 0010: API-Football Complete Stats")
    parser.add_argument("--dry-run", action="store_true", help="Muestra las sentencias sin ejecutar")
    args = parser.parse_args()
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
