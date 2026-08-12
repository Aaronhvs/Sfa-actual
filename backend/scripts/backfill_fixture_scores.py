"""Backfill authoritative fixture scores from API-Football.

Dry-run is the default. Use ``--apply`` only after a successful dry-run.
The command validates every requested fixture before writing any score.
"""
from __future__ import annotations

import argparse
import asyncio
import json

from sfa.application.use_cases.backfill_fixture_scores import (
    BackfillFixtureScoresUseCase,
)
from sfa.core.config import get_settings
from sfa.infrastructure.database import AsyncSessionLocal
from sfa.infrastructure.providers.api_football import APIFootballProvider
from sfa.infrastructure.repositories.fixture_score_backfill_repository import (
    FixtureScoreBackfillRepository,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--season",
        dest="seasons",
        action="append",
        required=True,
        help="Season to backfill; repeat for multiple seasons",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist validated scores; default is dry-run",
    )
    parser.add_argument("--batch-size", type=int, default=20)
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    provider = APIFootballProvider(
        settings.API_FOOTBALL_KEY,
        settings.API_FOOTBALL_BASE_URL,
    )
    try:
        async with AsyncSessionLocal() as session:
            use_case = BackfillFixtureScoresUseCase(
                FixtureScoreBackfillRepository(session),
                provider,
            )
            result = await use_case.execute(
                seasons=args.seasons,
                dry_run=not args.apply,
                batch_size=args.batch_size,
            )
            if result.status == "completed" and args.apply:
                await session.commit()
            else:
                await session.rollback()

        print(json.dumps({
            "seasons": result.seasons,
            "dry_run": result.dry_run,
            "requested": result.requested,
            "fetched": result.fetched,
            "validated": result.validated,
            "updated": result.updated,
            "missing_external_ids": result.missing_external_ids,
            "blockers": result.blockers,
            "status": result.status,
            "error": result.error,
        }, ensure_ascii=True))
        return 0 if result.status == "completed" else 1
    finally:
        await provider.close()


def main() -> None:
    raise SystemExit(asyncio.run(_run(_arguments())))


if __name__ == "__main__":
    main()
