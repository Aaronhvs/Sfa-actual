import asyncio,json,time
from pathlib import Path
from sqlalchemy import text
from sfa.infrastructure.database import engine,AsyncSessionLocal
from sfa.infrastructure.repositories.team_strength_repository import TeamStrengthRepository
from sfa.domain.scoring_ports import FixtureTeamStrengthDTO

async def main():
 async with engine.connect() as c:
  assert (await c.scalar(text('select current_database()'))).startswith('sfa_positions_validation_')
  exists=await c.scalar(text("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='position_correction_batches' AND column_name='guard_rules_version_id')"))
  if not exists:
   raw=await c.get_raw_connection()
   await raw.driver_connection.execute(Path('/code/migrations/0055_position_guard_hot_path.sql').read_text())
  await c.commit()
 async with AsyncSessionLocal() as session:
  assert await session.scalar(text("SELECT count(*) FROM position_correction_batches WHERE guard_rules_version_id IS DISTINCT FROM (manifest->>'rules_version_id')::integer OR guard_bonus_ids IS DISTINCT FROM ARRAY(SELECT (r->>'id')::bigint FROM jsonb_array_elements(coalesce(after_image->'bonuses','[]')) r) OR guard_rollup_ids IS DISTINCT FROM ARRAY(SELECT (r->>'id')::bigint FROM jsonb_array_elements(coalesce(after_image->'rollups','[]')) r)"))==0
  rows=(await session.execute(text("SELECT * FROM fixture_team_strengths WHERE season='2026' AND participant_kind='club' ORDER BY fixture_id,team_id"))).mappings().all()
  before=[dict(r) for r in rows]
  fields=('fixture_id','team_id','season','competition_id','participant_kind','pre_match_elo_raw','post_match_elo_raw','pre_match_strength','post_match_strength','model_version','seed_source')
  snapshots=[FixtureTeamStrengthDTO(*(r[k] for k in fields)) for r in rows]
  count=await session.scalar(text('select count(*) from player_position_evidence'))
  started=time.monotonic()
  await TeamStrengthRepository(session).replace_fixture_team_strengths('2026','club',sorted({r['competition_id'] for r in rows}),snapshots)
  after=[dict(r) for r in (await session.execute(text("SELECT * FROM fixture_team_strengths WHERE season='2026' AND participant_kind='club' ORDER BY fixture_id,team_id"))).mappings()]
  assert before==after,'Identical replay changed snapshot values/creation time'
  assert await session.scalar(text('select count(*) from player_position_evidence'))==count,'No-op generated candidates'
  print(json.dumps({'identical_snapshot_replay':len(rows),'seconds':round(time.monotonic()-started,3),'values_and_timestamps':'unchanged','candidates':'unchanged'}),flush=True)
  protected=await session.scalar(text("SELECT applicable_fixture_ids[1] FROM player_position_assignments a JOIN position_correction_batches b ON b.batch_id=a.publication_batch_id WHERE b.status='published' LIMIT 1"))
  original=(await session.execute(text('SELECT * FROM fixture_team_strengths WHERE fixture_id=:id LIMIT 1'),{'id':protected})).mappings().one()
  await session.execute(text('UPDATE fixture_team_strengths SET pre_match_elo_raw=pre_match_elo_raw+1 WHERE fixture_id=:id AND team_id=:team'),{'id':protected,'team':original['team_id']})
  actual=(await session.execute(text('SELECT * FROM fixture_team_strengths WHERE fixture_id=:id AND team_id=:team'),{'id':protected,'team':original['team_id']})).mappings().one()
  assert dict(actual)==dict(original)
  assert await session.scalar(text('select count(*) from player_position_evidence'))>count
  await session.rollback()
  print(json.dumps({'changed_protected_snapshot':'conserved','journal_projection_equivalence':'passed'}),flush=True)
 await engine.dispose()
asyncio.run(main())
