"""Promote or revert the offline 0069 staging cut. Defaults to a transaction rollback."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import text

from sfa.core.dependencies import get_season_integrity_publication_use_cases
from sfa.infrastructure.database import AsyncSessionLocal
from sfa.infrastructure.repositories.file_integrity_journal import FileIntegrityJournal


async def run(args):
    folder = Path(args.directory)
    async with AsyncSessionLocal() as session:
        session.info["position_publication_exclusive"] = True
        # Do not query the DB before the use case takes the exclusive, try-only lock.
        promote, revert = get_season_integrity_publication_use_cases(session, folder / "publication-journal")
        key, result = await (revert if args.revert else promote).execute()
        database = await session.scalar(text("SELECT current_database()"))
        if not database.endswith("_test") and not args.production:
            raise ValueError("Production publication requires explicit --production")
        if args.commit:
            await session.commit()
            await FileIntegrityJournal(folder / "publication-journal").write(
                key, "committed", json.dumps(asdict(result), sort_keys=True)
            )
        else:
            await session.rollback()
        print(json.dumps({"journal_key": key, "committed": args.commit, "result": asdict(result)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--revert", action="store_true")
    asyncio.run(run(parser.parse_args()))
