"""Complete audit capture, independent of public ranking eligibility filters."""
from dataclasses import asdict
import json
from sqlalchemy import text
from sfa.domain.player_positions.publication import canonical, digest
from sfa.domain.player_positions.value_objects import PositionAuditSnapshot


class ActiveSeasonPositionSnapshotSource:
    def __init__(self, session, scopes, rules, scores, events):
        self._session,self._scopes,self._rules,self._scores,self._events=session,scopes,rules,scores,events

    async def load(self) -> PositionAuditSnapshot:
        scope=await self._scopes.resolve_scope('season-2026')
        if scope.key!='season-2026' or any(s!='2026' or c==350 for s,c in scope.pairs):
            raise ValueError('Capture is restricted to the approved club period')
        active=await self._rules.get_active_version()
        version=await self._scores.resolve_rules_version_id_for_scope(scope,active.id)
        params={'version':version,'scope':scope.key,'season':'2026',
                'comps':sorted(c for _,c in scope.pairs)}
        clauses=[]
        for i,(season,comp) in enumerate(sorted(scope.pairs)):
            params[f's{i}']=season;params[f'c{i}']=comp
            clauses.append(f'(x.season=:s{i} AND x.competition_id=:c{i})')
        period='('+' OR '.join(clauses)+')'
        async def query(sql):
            return list((await self._session.execute(text('SELECT to_jsonb(q) FROM ('+sql+')q'),params)).scalars())
        async def table(name,where='true'):
            return await query(f'SELECT x.* FROM {name} x WHERE {where} ORDER BY id')
        rolls=await table('sfa_season_scores',period+' AND x.rules_version_id=:version')
        persisted=await table('player_event_scores',period+' AND x.rules_version_id=:version')
        fixtures=await table('fixtures',period)
        fixture_ids=','.join(str(f['id']) for f in fixtures) or '0'
        player_ids=','.join(str(p) for p in sorted({r['player_id'] for r in rolls})) or '0'
        players=await table('players',f'x.id IN ({player_ids})')
        stats=await table('player_stats',f'x.fixture_id IN ({fixture_ids})')
        snapshots=await table('fixture_lineup_snapshots',f'x.fixture_id IN ({fixture_ids})')
        assignments=await table('player_position_assignments',f'x.player_id IN ({player_ids})')
        arbitrations=await table('position_lineup_arbitrations',f'x.fixture_id IN ({fixture_ids})')
        classifications=await table('position_scope_classifications','x.scope_key=:scope')
        corrections=await query("SELECT batch_id,status,published_at,guard_rules_version_id AS rules_version_id,after_image "
                                "FROM position_correction_batches x ORDER BY published_at,batch_id")
        achievements=await table('competition_achievements',period)
        bonuses=await table('player_achievement_bonuses',period+' AND x.rules_version_id=:version')
        honors=await table('individual_honors','x.scope_key=:scope AND x.rules_version_id=:version')
        # Intentionally includes zero/negative totals and 1-2 appearances. This
        # internal capture cannot borrow the public ranking's eligibility rules.
        ranking=await query(f"""
            WITH totals AS (SELECT x.player_id,sum(x.total_pts+coalesce(x.achievement_bonus_pts,0)) pts,
                                sum(x.matches_played) matches
              FROM sfa_season_scores x WHERE {period} AND x.rules_version_id=:version GROUP BY x.player_id),
            honors AS (SELECT player_id,sum(awarded_bonus_pts) pts FROM individual_honors
              WHERE scope_key=:scope AND rules_version_id=:version GROUP BY player_id),
            combined AS (SELECT t.*,t.pts+coalesce(h.pts,0) total_pts FROM totals t
              LEFT JOIN honors h ON h.player_id=t.player_id)
            SELECT rank() OVER(ORDER BY t.total_pts DESC) rank,p.id player_id,p.name player_name,t.total_pts,
              t.matches matches_played,sfa_scope_position(p.id,:scope,NULL,CAST(:comps AS integer[]),
                sfa_current_position(p.id,NULL,:season,now())) position
            FROM combined t JOIN players p ON p.id=t.player_id ORDER BY t.total_pts DESC,p.id
        """)
        raw=[];unavailable=[]
        for season,comp in sorted(scope.pairs):
            try:
                raw.extend(asdict(r) for r in await self._events.get_events_for_recalc(season,comp,None,None))
            except ValueError:
                for fixture in fixtures:
                    if fixture['season']!=season or fixture['competition_id']!=comp:continue
                    try:
                        raw.extend(asdict(r) for r in await self._events.get_events_for_recalc(season,comp,fixture['id'],None))
                    except ValueError as error:
                        unavailable.append({'fixture_id':fixture['id'],'reason':str(error)})
        meta=await self._session.scalar(text("SELECT json_build_object('captured_at',now(),'isolation',"
            "current_setting('transaction_isolation'),'read_only',current_setting('transaction_read_only'))"))
        if meta['read_only']!='on' or meta['isolation']!='repeatable read':
            raise ValueError('Capture requires the input adapter to open READ ONLY/REPEATABLE READ first')
        result={'schema':'active-season-position-impact-v1','meta':meta,'scope':asdict(scope),'version':version,
                'use_total':True,'ranking':ranking,'players':players,'fixtures':fixtures,'stats':stats,
                'snapshots':snapshots,'assignments':assignments,'lineup_arbitrations':arbitrations,
                'scope_classifications':classifications,'rollups':rolls,'scores':persisted,'raw_events':raw,
                'published_corrections':corrections,
                'unavailable_raw_fixtures':unavailable,'achievements':achievements,'bonuses':bonuses,'honors':honors,
                'teams':await table('teams'),'competitions':await table('competitions'),
                'rules':await table('scoring_rules_versions','x.id=:version'),'provider_requests':0,'writes':0}
        result=json.loads(json.dumps(result,default=lambda v: sorted(v) if isinstance(v,(set,frozenset)) else str(v)))
        return PositionAuditSnapshot(canonical(result),digest(result))
