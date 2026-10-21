"""Prepare, apply or compensate the approved season-2026 pilot; never fetches upstream."""
from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from sfa.core.dependencies import get_season_position_correction_use_cases, get_active_season_position_snapshot_source
from sfa.domain.player_positions.publication import SeasonPositionCorrectionPlan
from sfa.infrastructure.database import AsyncSessionLocal, engine
from sfa.infrastructure.repositories.season_position_correction_repository import engine_hash


async def run(args):
    async with AsyncSessionLocal(info={'position_publication_exclusive': args.action not in {'prepare','capture'}}) as session:
        compiler, publisher, reverter, repo = get_season_position_correction_use_cases(session)
        if args.action == 'capture':
            await session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            snapshot=await get_active_season_position_snapshot_source(session).load()
            with Path(args.output).open('x',encoding='utf8') as target:target.write(snapshot.content)
            print(json.dumps({'status':'captured','sha256':snapshot.sha256,'provider_requests':0,'writes':0}))
        elif args.action == 'prepare':
            await session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            data = json.loads(Path(args.inputs).read_text('utf8'))
            await repo.validate_snapshot(data['snapshot'])
            source = await repo.fingerprint(json.dumps(data['snapshot']['scope']), data['snapshot']['version'])
            plan = await compiler.execute(**data, source_hash=source, engine_hash=engine_hash(),
                                    actor=args.actor, accepted_at=datetime.now(timezone.utc).isoformat())
            Path(args.output).write_text(json.dumps(asdict(plan), ensure_ascii=False, indent=2), 'utf8')
            report=json.loads(plan.report_json)
            print(json.dumps({'batch_id':plan.batch_id,'source_hash':plan.source_hash,'engine_hash':plan.engine_hash,
                              'counts':{k:report[k] for k in ('selected_classifications','journal_events',
                                        'journal_rollups','journal_bonuses','changed_events','changed_players')}}))
        elif args.action == 'publish':
            plan = SeasonPositionCorrectionPlan(**json.loads(Path(args.manifest).read_text('utf8')))
            if args.expected_hash != plan.manifest_hash:
                raise ValueError('Manifest SHA256 mismatch')
            result = await publisher.execute(plan)
            await session.commit()
            print(json.dumps(asdict(result)))
        else:
            result = await reverter.execute(args.batch_id, args.actor)
            await session.commit()
            print(json.dumps(asdict(result)))
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    capture=commands.add_parser('capture');capture.add_argument('output')
    prepare = commands.add_parser('prepare')
    prepare.add_argument('inputs')
    prepare.add_argument('output')
    prepare.add_argument('--actor', required=True)
    publish = commands.add_parser('publish')
    publish.add_argument('manifest')
    publish.add_argument('--expected-hash', required=True)
    revert = commands.add_parser('revert')
    revert.add_argument('batch_id')
    revert.add_argument('--actor', required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == '__main__':
    main()
