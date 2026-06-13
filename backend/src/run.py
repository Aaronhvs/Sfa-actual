"""
CLI de administración SFA.

Uso:
    python src/run.py --recalculate                        # todas las competiciones
    python src/run.py --recalculate --competition-id 3    # una competición
    python src/run.py --recalculate --season 2024         # una temporada
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time

from sqlalchemy import select

from sfa.application.use_cases.recalculate_scores import RecalculateScoresUseCase
from sfa.infrastructure.database import AsyncSessionLocal
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.scores.models import SFASeasonScore
from sfa.infrastructure.repositories.enrichment_repository import EnrichmentRepository


async def _get_competition_name(session, competition_id: int) -> str:
    row = await session.execute(
        select(Competition.name).where(Competition.id == competition_id)
    )
    result = row.scalar_one_or_none()
    return result or f"competition_id={competition_id}"


async def run_recalculate(
    competition_id: int | None,
    season: str | None,
) -> None:
    async with AsyncSessionLocal() as session:
        # Discover all (competition_id, season) pairs to process
        stmt = (
            select(SFASeasonScore.competition_id, SFASeasonScore.season)
            .distinct()
            .order_by(SFASeasonScore.competition_id, SFASeasonScore.season)
        )
        if competition_id is not None:
            stmt = stmt.where(SFASeasonScore.competition_id == competition_id)
        if season is not None:
            stmt = stmt.where(SFASeasonScore.season == season)

        pairs = (await session.execute(stmt)).fetchall()

    if not pairs:
        print("No se encontraron datos para los filtros indicados.")
        sys.exit(0)

    print(f"\n{'─' * 60}")
    print(f"  SFA — Recálculo de puntuaciones")
    print(f"  {len(pairs)} par(es) competición/temporada a procesar")
    print(f"{'─' * 60}\n")

    total_events = 0
    total_scores = 0
    t_global = time.perf_counter()

    for comp_id, seas in pairs:
        async with AsyncSessionLocal() as session:
            comp_name = await _get_competition_name(session, comp_id)

            repo = EnrichmentRepository(session)
            use_case = RecalculateScoresUseCase(repo)

            t0 = time.perf_counter()
            result = await use_case.execute(comp_id, seas)
            await session.commit()
            elapsed = time.perf_counter() - t0

        total_events += result.events_updated
        total_scores += result.scores_updated

        status = "✓" if result.events_updated > 0 else "·"
        print(
            f"  {status}  {comp_name:<30}  {seas}  "
            f"events={result.events_updated:>4}  "
            f"scores={result.scores_updated:>4}  "
            f"({elapsed:.2f}s)"
        )

    elapsed_total = time.perf_counter() - t_global
    print(f"\n{'─' * 60}")
    print(f"  Total events actualizados : {total_events}")
    print(f"  Total scores actualizados : {total_scores}")
    print(f"  Tiempo total              : {elapsed_total:.2f}s")
    print(f"{'─' * 60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI de administración SFA")
    parser.add_argument(
        "--recalculate",
        action="store_true",
        help="Recalcula puntuaciones SFA con la tabla de puntos actual",
    )
    parser.add_argument(
        "--competition-id",
        type=int,
        default=None,
        metavar="ID",
        help="Limitar a una competición concreta",
    )
    parser.add_argument(
        "--season",
        type=str,
        default=None,
        help="Limitar a una temporada concreta (ej. 2024)",
    )
    args = parser.parse_args()

    if not args.recalculate:
        parser.print_help()
        sys.exit(0)

    asyncio.run(run_recalculate(args.competition_id, args.season))


if __name__ == "__main__":
    main()
