"""Input adapter for explicitly approved curated correction manifests.

Examples (PYTHONPATH=src):
  python scripts/publish_position_correction.py preview request.json manifest.json --rules-version 4
  python scripts/publish_position_correction.py publish manifest.json --approved-hash <sha256>
  python scripts/publish_position_correction.py revert <batch-sha256> --actor <reviewer>
"""
from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import text

from sfa.core.dependencies import get_position_correction_use_cases
from sfa.domain.player_positions.publication import PositionCorrectionPlan, PositionCorrectionRequest
from sfa.infrastructure.database import AsyncSessionLocal, engine


async def run(args):
    async with AsyncSessionLocal(info={"position_publication_exclusive": args.action != "preview"}) as session:
        simulation, publication, reversal = get_position_correction_use_cases(session)
        if args.action == "preview":
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            data = json.loads(Path(args.request).read_text("utf-8"))
            data["fixture_ids"] = tuple(data["fixture_ids"])
            plan = await simulation.execute(PositionCorrectionRequest(**data), args.rules_version)
            Path(args.output).write_text(json.dumps(asdict(plan), indent=2, ensure_ascii=False), "utf-8")
            result = {"status": "preview", "manifest_hash": plan.manifest_hash, "report": json.loads(plan.report_json)}
        elif args.action == "publish":
            data = json.loads(Path(args.manifest).read_text("utf-8"))
            request = data.pop("request")
            request.setdefault("schema_version", 1)
            request["fixture_ids"] = tuple(request["fixture_ids"])
            plan = PositionCorrectionPlan(request=PositionCorrectionRequest(**request), **data)
            if not args.approved_hash or args.approved_hash != plan.manifest_hash:
                raise ValueError("Publication requires explicit approval of this exact manifest SHA256")
            result = asdict(await publication.execute(plan))
            await session.commit()
        else:
            result = asdict(await reversal.execute(args.batch_id, args.actor))
            await session.commit()
        print(json.dumps(result, ensure_ascii=False))
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    preview = commands.add_parser("preview")
    preview.add_argument("request")
    preview.add_argument("output")
    preview.add_argument("--rules-version", type=int, required=True)
    publish = commands.add_parser("publish")
    publish.add_argument("manifest")
    publish.add_argument("--approved-hash", required=True)
    revert = commands.add_parser("revert")
    revert.add_argument("batch_id")
    revert.add_argument("--actor", required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
