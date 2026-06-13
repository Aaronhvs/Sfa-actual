"""
Migración 0022 — Activar scoring rules v2 como versión activa

Desactiva v1 (id=2) y activa v2 (id=3, v2.0-impact-model) con soporte
nativo para posiciones MCO, DEL, EXT, LAT, DC.

Uso:
    docker exec backend-api-1 python3 scripts/migrate_0022_activate_scoring_v2.py
    docker exec backend-api-1 python3 scripts/migrate_0022_activate_scoring_v2.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import text

sys.path.insert(0, "src")

from sfa.infrastructure.database import AsyncSessionLocal  # noqa: E402


async def run(dry_run: bool) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT id, name, version, is_active FROM scoring_rules_versions ORDER BY id")
        )
        rows = result.fetchall()
        print("Estado actual:")
        for row in rows:
            print(f"  id={row.id}  name={row.name}  version={row.version}  is_active={row.is_active}")

        if dry_run:
            print("\n[DRY RUN] Se ejecutaría:")
            print("  UPDATE scoring_rules_versions SET is_active = FALSE")
            print("  UPDATE scoring_rules_versions SET is_active = TRUE WHERE id = 3")
            return

        await session.execute(text("UPDATE scoring_rules_versions SET is_active = FALSE"))
        await session.execute(text("UPDATE scoring_rules_versions SET is_active = TRUE WHERE id = 3"))
        await session.commit()

        result = await session.execute(
            text("SELECT id, name, version, is_active FROM scoring_rules_versions ORDER BY id")
        )
        rows = result.fetchall()
        print("\nEstado tras la migración:")
        for row in rows:
            marker = " ← ACTIVA" if row.is_active else ""
            print(f"  id={row.id}  name={row.name}  version={row.version}  is_active={row.is_active}{marker}")

        print("\nMigración completada.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.dry_run))
