"""Acquire a bounded batch of missing lineups and keep immutable local evidence."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from sfa.core.dependencies import get_recover_position_lineups_use_case


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--season", required=True)
    parser.add_argument("--team-external-id", required=True, type=int)
    parser.add_argument("--ssh-host", default="sfa-vps")
    parser.add_argument("--max-fixtures", default=10, type=int)
    args = parser.parse_args()
    before = hashlib.sha256(args.snapshot.read_bytes()).hexdigest()
    use_case = get_recover_position_lineups_use_case(args.snapshot, args.output, args.ssh_host)
    outcome = await use_case.execute(season=args.season, team_external_id=args.team_external_id,
                                     max_fixtures=args.max_fixtures)
    if hashlib.sha256(args.snapshot.read_bytes()).hexdigest() != before:
        raise RuntimeError("Original snapshot changed during recovery")
    (args.output / "recovery-summary.json").write_text(outcome.summary_json + "\n", encoding="utf-8")
    result = json.loads(outcome.summary_json)
    print(json.dumps({key: result[key] for key in ("state", "selected_fixture_ids", "fixtures", "acquisition",
                                                  "http_calls_this_execution")}))


if __name__ == "__main__":
    asyncio.run(main())
