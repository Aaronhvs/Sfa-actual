"""Real, destructive-only-in-clone checks for the closed season correction batch."""
from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import text

from sfa.core.dependencies import get_season_position_correction_use_cases
from sfa.domain.player_positions.publication import SeasonPositionCorrectionPlan
from sfa.infrastructure.database import AsyncSessionLocal, engine


async def hashes(session, excluded=None):
    result={}
    for table in ('players','player_events','player_stats','player_event_scores','sfa_season_scores',
                  'player_achievement_bonuses','individual_honors','scoring_rules_versions'):
        ids=(excluded or {}).get(table,[])
        where=' WHERE id NOT IN ('+','.join(str(int(i)) for i in ids)+')' if ids else ''
        result[table]=list((await session.execute(text(f"SELECT count(*),md5(coalesce(string_agg("
            f"md5(to_jsonb(t)::text),'' ORDER BY id),'')) FROM {table} t{where}"))).one())
    return result


async def check(manifest, *, leave_published=False):
    plan=SeasonPositionCorrectionPlan(**json.loads(Path(manifest).read_text()))
    async with AsyncSessionLocal(info={'position_publication_exclusive':True}) as session:
        assert (await session.scalar(text('SELECT current_database()'))).startswith('sfa_positions_validation_')
        compiler,publisher,reverter,repo=get_season_position_correction_use_cases(session)
        excluded={table:[c['before']['id'] for c in json.loads(encoded)] for table,encoded in (
            ('player_event_scores',plan.event_changes_json),('sfa_season_scores',plan.rollup_changes_json),
            ('player_achievement_bonuses',plan.bonus_changes_json))}
        expected_before={'events':[c['before'] for c in json.loads(plan.event_changes_json)],
                         'rollups':[c['before'] for c in json.loads(plan.rollup_changes_json)],
                         'bonuses':[c['before'] for c in json.loads(plan.bonus_changes_json)]}
        before=await hashes(session,excluded)
        print('clone: baseline hashes complete',flush=True)
        assert await repo.fingerprint(plan.scope_json,plan.rules_version_id)==plan.source_hash
        session.info['position_publication_failpoint']='after_events'
        try:
            await publisher.execute(plan)
        except RuntimeError as error:
            assert 'failpoint' in str(error)
        else:
            raise AssertionError('Failpoint did not fire')
        await session.rollback()
        session.info.pop('position_publication_failpoint')
        assert await hashes(session,excluded)==before
        restored=await repo._image_for(expected_before)
        assert all({r['id']:r for r in restored[k]}=={r['id']:r for r in expected_before[k]} for k in expected_before)
        assert await repo.published(plan.batch_id) is None
        print('clone: full failpoint rollback verified',flush=True)
        await session.execute(text("UPDATE players SET photo_url=coalesce(photo_url,'')||'?clone-cas' WHERE id=35"))
        try:
            await publisher.execute(plan)
        except ValueError as error:
            assert 'changed' in str(error)
        else:
            raise AssertionError('Source CAS failed')
        await session.rollback()
        print('clone: source CAS rejection verified',flush=True)
        result=await publisher.execute(plan)
        assert await publisher.execute(plan)==result
        await session.commit()
        print('clone: publication committed and idempotence verified',flush=True)
        assert await session.scalar(text('SELECT count(*) FROM position_scope_classifications WHERE batch_id=:id'),
                                    {'id':plan.batch_id})==len(json.loads(plan.classifications_json))
        for pid,expected in ((35,'DEL'),(7571,'DEL'),(75,'DEL'),(42541,'MC'),(52,'MCO'),(517,'MCO')):
            default=await session.scalar(text("SELECT sfa_current_position(:p,NULL,'2026',now())"),{'p':pid})
            actual=await session.scalar(text('SELECT sfa_scope_position(:p,:scope,NULL,:comps,:fallback)'),
                {'p':pid,'scope':'season-2026','comps':json.loads(plan.classifications_json)[0]['scope_competition_ids'],
                 'fallback':default})
            assert actual==expected,(pid,actual)
        first=json.loads(plan.event_changes_json)[0]
        assert await session.scalar(text('SELECT sfa_fixture_scoring_position(:p,:f,:fallback)'),
            {'p':first['after']['player_id'],'f':first['after']['fixture_id'],'fallback':'MC'})==first['after']['position']
        await session.execute(text("SELECT set_config('sfa.position_publication','on',true)"))
        try:
            async with session.begin_nested():
                await session.execute(text("""
                    INSERT INTO position_lineup_arbitrations(fixture_id,team_id,active_snapshot_id,
                      compatible_snapshot_ids,revision_id,source_ref,fetched_at,supersedes,reason,actor)
                    SELECT a.fixture_id,a.team_id,s.id,ARRAY[s.id],repeat('f',64),'clone:tie',a.fetched_at,
                           '[]','clone:tie','clone-check'
                    FROM position_lineup_arbitrations a JOIN fixture_lineup_snapshots s
                      ON s.fixture_id=a.fixture_id AND s.team_id=a.team_id
                    WHERE NOT s.id=ANY(a.compatible_snapshot_ids) LIMIT 1
                """))
        except Exception as error:
            assert 'Equal-time incompatible' in str(error)
        else:
            raise AssertionError('Equal-time provider conflict was not quarantined')
        await session.execute(text("SELECT set_config('sfa.position_publication','off',true)"))
        after=await hashes(session,excluded)
        assert all(before[t]==after[t] for t in ('players','player_events','player_stats','individual_honors','scoring_rules_versions'))
        # An attempted stale writer must preserve curated rows and retain its candidate.
        await session.execute(text('UPDATE player_event_scores SET final_points=final_points+1 WHERE id=:id'),
                              {'id':first['after']['id']})
        await session.execute(text('DELETE FROM player_events WHERE id=:id'),{'id':first['after']['event_id']})
        assert await session.scalar(text('SELECT final_points FROM player_event_scores WHERE id=:id'),
                                    {'id':first['after']['id']})==Decimal(str(first['after']['final_points']))
        assert await session.scalar(text("SELECT count(*) FROM player_position_evidence WHERE assertion_kind='dependency_update_candidate'"))>0
        await session.rollback()
        print('clone: protected writer candidates verified',flush=True)
        # Moving a protected OLD identity must not evade its conservation guard.
        bonus=json.loads(plan.bonus_changes_json)[0]['after']
        await session.execute(text('UPDATE player_achievement_bonuses SET player_id=35,rules_version_id=1 WHERE id=:id'),
                              {'id':bonus['id']})
        assert await session.scalar(text('SELECT player_id FROM player_achievement_bonuses WHERE id=:id'),
                                    {'id':bonus['id']})==bonus['player_id']
        selected={d['player_id'] for d in json.loads(plan.decisions_json)}
        peer=next(c['after'] for c in json.loads(plan.rollup_changes_json) if c['after']['player_id'] not in selected)
        await session.execute(text("UPDATE sfa_season_scores SET player_id=35,season='1900',competition_id=350 WHERE id=:id"),
                              {'id':peer['id']})
        assert await session.scalar(text('SELECT player_id FROM sfa_season_scores WHERE id=:id'),
                                    {'id':peer['id']})==peer['player_id']
        await session.rollback()
        print('clone: OLD bonus/peer identities preserved',flush=True)
        # A sanctioned subsequent change makes compensation fail instead of overwriting it.
        await session.execute(text("SELECT set_config('sfa.position_publication','on',true)"))
        await session.execute(text('UPDATE player_event_scores SET final_points=final_points+1 WHERE id=:id'),
                              {'id':first['after']['id']})
        try:
            await reverter.execute(plan.batch_id,'clone-check')
        except ValueError as error:
            assert 'Postimages changed' in str(error)
        else:
            raise AssertionError('Compensation overwrote a later change')
        await session.rollback()
        if not leave_published:
            reverted=await reverter.execute(plan.batch_id,'clone-check')
            await session.commit()
            assert reverted.status=='reverted' and await hashes(session,excluded)==before
            journal=(await session.execute(text('SELECT before_image FROM position_correction_batches WHERE batch_id=:id'),
                                           {'id':plan.batch_id})).scalar_one()
            restored=await repo._image_for(journal)
            # JSONB compares numbers by value; its textual numeric scale is not a
            # data mutation. Every full affected row must equal the before image.
            assert all({r['id']:r for r in restored[k]}=={r['id']:r for r in journal[k]} for k in ('events','rollups','bonuses','explanations'))
            assert (await reverter.execute(plan.batch_id,'clone-check')).status=='reverted'
        else:
            await session.rollback()
        print(json.dumps({'batch_id':plan.batch_id,'checks':'atomicity,CAS,idempotence,scope-labels,writer-conservation,revert-CAS,exact-reversal',
                          'result':asdict(result),'left_published':leave_published}),flush=True)
    await engine.dispose()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest');parser.add_argument('--leave-published',action='store_true')
    args=parser.parse_args()
    asyncio.run(check(args.manifest,leave_published=args.leave_published))
