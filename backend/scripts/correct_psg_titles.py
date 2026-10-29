"""0070 private title repair. Offline captures only; dry run rolls back by default."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import text

from sfa.core.dependencies import get_competition_title_correction_use_cases
from sfa.domain.title_correction import TitleCorrectionSnapshot
from sfa.infrastructure.database import AsyncSessionLocal
from sfa.infrastructure.repositories.file_integrity_journal import FileIntegrityJournal

CAPTURES = ("supercup-final", "ligue1-fixtures", "ligue1-standings",
            "intercontinental-fixtures", "intercontinental-players")


async def run(args):
    directory = Path(args.directory)
    evidence = json.dumps({name: json.loads((directory / (name + ".json")).read_text()) for name in CAPTURES})
    async with AsyncSessionLocal() as session:
        session.info["position_publication_exclusive"] = True
        prepare, apply = get_competition_title_correction_use_cases(session, directory / "title-journal")
        if args.revert:
            intent = json.loads((directory / "title-journal" / (args.revert + "-intent.json")).read_text())
            prepared = json.loads((directory / "title-journal" / (args.revert + "-prepared.json")).read_text())
            plan = json.loads(intent["payload"])
            before = TitleCorrectionSnapshot(**plan["before"])
            after = TitleCorrectionSnapshot(**json.loads(prepared["payload"]))
            key = await apply.revert(before, after, evidence)
            result = before
        else:
            plan = await prepare.execute(evidence)
            if args.expected_fingerprint and plan.before.fingerprint != args.expected_fingerprint:
                raise ValueError("Prepared cut changed; repeat the dry run")
            key, result = await apply.execute(plan)
            print(json.dumps({"before_fingerprint": plan.before.fingerprint}), flush=True)
        database = await session.scalar(text("SELECT current_database()"))
        if not database.endswith("_test") and not args.production:
            raise ValueError("Production requires --production; transaction rolled back")
        if args.commit:
            await session.commit()
            await FileIntegrityJournal(directory / "title-journal").write(
                key, "committed", json.dumps(asdict(result), sort_keys=True),
            )
        else:
            await session.rollback()
        print(json.dumps({"journal_key": key, "committed": args.commit,
                          "after_fingerprint": result.fingerprint}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--expected-fingerprint")
    parser.add_argument("--revert", help="Committed journal key to revert with strict CAS")
    asyncio.run(run(parser.parse_args()))
