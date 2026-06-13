"""
Recalcula el SFASeasonScore de un jugador específico usando datos ya en la DB.

No llama a ninguna API externa. Lee PlayerEvents y PlayerStats existentes,
reconcilia los conteos de goles/asistencias con los valores reales de PlayerStats,
y actualiza sfa_season_scores.

Uso:
    cd backend
    python scripts/recompute_player_score.py "Yamal"
    python scripts/recompute_player_score.py "Lamine Yamal" --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone

from sqlalchemy import func, select, update

# Permite ejecutar desde el directorio backend con python scripts/...
sys.path.insert(0, "src")

from sfa.infrastructure.database import AsyncSessionLocal  # noqa: E402
from sfa.infrastructure.models.events.models import PlayerEvent  # noqa: E402
from sfa.infrastructure.models.fixtures.models import Fixture  # noqa: E402
from sfa.infrastructure.models.player_stats.models import PlayerStats  # noqa: E402
from sfa.infrastructure.models.players.models import Player  # noqa: E402
from sfa.infrastructure.models.scores.models import SFASeasonScore  # noqa: E402


def _reconcile_breakdown_counts(
    breakdown: dict, real_goals: int, real_assists: int
) -> None:
    event_goals = (
        breakdown.get("goal", {}).get("count", 0)
        + breakdown.get("goal_penalty", {}).get("count", 0)
    )
    missing_goals = real_goals - event_goals
    if missing_goals > 0:
        if "goal" not in breakdown:
            breakdown["goal"] = {"count": 0, "pts": 0.0}
        breakdown["goal"]["count"] += missing_goals

    event_assists = (
        breakdown.get("assist", {}).get("count", 0)
        + breakdown.get("corner_assist", {}).get("count", 0)
    )
    missing_assists = real_assists - event_assists
    if missing_assists > 0:
        if "assist" not in breakdown:
            breakdown["assist"] = {"count": 0, "pts": 0.0}
        breakdown["assist"]["count"] += missing_assists


async def recompute(player_name_pattern: str, dry_run: bool) -> None:
    async with AsyncSessionLocal() as session:
        # 1. Buscar jugador(es) por nombre
        players_stmt = select(Player).where(
            Player.name.ilike(f"%{player_name_pattern}%")
        )
        players = (await session.execute(players_stmt)).scalars().all()

        if not players:
            print(f"[!] No se encontró ningún jugador con '{player_name_pattern}'")
            return

        for player in players:
            print(f"\n{'='*60}")
            print(f"Jugador: {player.name}  (id={player.id})")
            print(f"{'='*60}")

            # 2. Obtener todos sus SFASeasonScore
            scores_stmt = select(SFASeasonScore).where(
                SFASeasonScore.player_id == player.id
            )
            scores = (await session.execute(scores_stmt)).scalars().all()

            if not scores:
                print("  Sin season scores en la DB.")
                continue

            for score in scores:
                print(f"\n  Competición id={score.competition_id}  temporada={score.season}")

                old_bd = score.breakdown or {}
                old_goals = (
                    old_bd.get("goal", {}).get("count", 0)
                    + old_bd.get("goal_penalty", {}).get("count", 0)
                )
                old_assists = (
                    old_bd.get("assist", {}).get("count", 0)
                    + old_bd.get("corner_assist", {}).get("count", 0)
                )
                print(f"  ANTES  → partidos={score.matches_played}  goles={old_goals}  asistencias={old_assists}")

                # 3. Reconstruir breakdown desde PlayerEvents
                events_stmt = (
                    select(PlayerEvent.event_type, PlayerEvent.pts)
                    .join(Fixture, Fixture.id == PlayerEvent.fixture_id)
                    .where(
                        PlayerEvent.player_id == player.id,
                        Fixture.competition_id == score.competition_id,
                        Fixture.season == score.season,
                    )
                )
                events = (await session.execute(events_stmt)).fetchall()

                new_breakdown: dict[str, dict] = {}
                new_total_pts = 0.0
                for evt_type, pts in events:
                    key = evt_type.value if hasattr(evt_type, "value") else str(evt_type)
                    key = key.lower()
                    if key not in new_breakdown:
                        new_breakdown[key] = {"count": 0, "pts": 0.0}
                    new_breakdown[key]["count"] += 1
                    new_breakdown[key]["pts"] = round(new_breakdown[key]["pts"] + float(pts), 2)
                    new_total_pts += float(pts)

                new_total_pts = round(new_total_pts, 2)

                # 4. Obtener goles y asistencias reales de PlayerStats
                stats_stmt = (
                    select(
                        func.coalesce(func.sum(PlayerStats.goals), 0).label("goals"),
                        func.coalesce(func.sum(PlayerStats.assists), 0).label("assists"),
                        func.count(PlayerStats.fixture_id).label("matches"),
                    )
                    .join(Fixture, Fixture.id == PlayerStats.fixture_id)
                    .where(
                        PlayerStats.player_id == player.id,
                        PlayerStats.season == score.season,
                        Fixture.competition_id == score.competition_id,
                    )
                )
                stats_row = (await session.execute(stats_stmt)).mappings().first()
                real_goals = int(stats_row["goals"]) if stats_row else 0
                real_assists = int(stats_row["assists"]) if stats_row else 0
                real_matches = int(stats_row["matches"]) if stats_row else score.matches_played

                print(f"  PlayerStats (fuente real) → goles={real_goals}  asistencias={real_assists}  fixtures con stats={real_matches}")

                # 5. Reconciliar conteos
                _reconcile_breakdown_counts(new_breakdown, real_goals, real_assists)

                # 6. Calcular porcentajes
                for key in new_breakdown:
                    pct = (
                        round(new_breakdown[key]["pts"] / new_total_pts * 100, 1)
                        if new_total_pts > 0 else 0.0
                    )
                    new_breakdown[key]["pct"] = pct

                new_goals = (
                    new_breakdown.get("goal", {}).get("count", 0)
                    + new_breakdown.get("goal_penalty", {}).get("count", 0)
                )
                new_assists = (
                    new_breakdown.get("assist", {}).get("count", 0)
                    + new_breakdown.get("corner_assist", {}).get("count", 0)
                )
                print(f"  DESPUÉS → partidos={real_matches}  goles={new_goals}  asistencias={new_assists}  pts={new_total_pts}")

                if not dry_run:
                    await session.execute(
                        update(SFASeasonScore)
                        .where(SFASeasonScore.id == score.id)
                        .values(
                            matches_played=real_matches,
                            breakdown=new_breakdown,
                            last_updated=datetime.now(timezone.utc),
                        )
                    )
                    print("  [OK] SFASeasonScore actualizado.")
                else:
                    print("  [DRY-RUN] No se escribió en la DB.")

        if not dry_run:
            await session.commit()
            print("\nCommit realizado.")
        else:
            print("\nDRY-RUN: ningún cambio en la DB.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Recalcula SFASeasonScore de un jugador desde la DB.")
    parser.add_argument("player", help="Nombre o parte del nombre del jugador")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Muestra los cambios sin escribir en la DB"
    )
    args = parser.parse_args()
    asyncio.run(recompute(args.player, args.dry_run))


if __name__ == "__main__":
    main()
