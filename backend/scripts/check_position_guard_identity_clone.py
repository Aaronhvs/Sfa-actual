import asyncio,json
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sfa.infrastructure.database import AsyncSessionLocal,engine
async def main():
 async with AsyncSessionLocal() as s:
  assert (await s.scalar(text('select current_database()'))).startswith('sfa_positions_validation_')
  for table,array in (('player_achievement_bonuses','guard_bonus_ids'),('sfa_season_scores','guard_rollup_ids')):
   row=(await s.execute(text(f"SELECT x.* FROM {table} x JOIN position_correction_batches b ON x.id=ANY(b.{array}) AND b.status='published' LIMIT 1"))).mappings().one()
   replacement=await s.scalar(text('SELECT id FROM players WHERE id<>:id ORDER BY id LIMIT 1'),{'id':row['player_id']})
   await s.execute(text(f'UPDATE {table} SET player_id=:new WHERE id=:id'),{'new':replacement,'id':row['id']})
   current=(await s.execute(text(f'SELECT * FROM {table} WHERE id=:id'),{'id':row['id']})).mappings().one()
   assert dict(current)==dict(row),table
   await s.execute(text(f'DELETE FROM {table} WHERE id=:id'),{'id':row['id']})
   assert await s.scalar(text(f'SELECT count(*) FROM {table} WHERE id=:id'),{'id':row['id']})==1
  protected=(await s.execute(text("SELECT f.* FROM fixture_team_strengths f JOIN player_position_assignments a ON f.fixture_id=ANY(a.applicable_fixture_ids) JOIN position_correction_batches b ON b.batch_id=a.publication_batch_id WHERE b.status='published' LIMIT 1"))).mappings().one()
  other=await s.scalar(text('SELECT id FROM fixtures WHERE id<>:id LIMIT 1'),{'id':protected['fixture_id']})
  await s.execute(text('UPDATE fixture_team_strengths SET fixture_id=:other WHERE fixture_id=:id AND team_id=:team'),{'other':other,'id':protected['fixture_id'],'team':protected['team_id']})
  current=(await s.execute(text('SELECT * FROM fixture_team_strengths WHERE fixture_id=:id AND team_id=:team'),{'id':protected['fixture_id'],'team':protected['team_id']})).mappings().one()
  assert dict(current)==dict(protected)
  for payload in ('{"bonuses":null}','{"bonuses":[{}]}','{"bonuses":[{"id":1},{"id":1}]}'):
   try:
    async with s.begin_nested():await s.scalar(text("SELECT position_guard_ids(CAST(:payload AS jsonb),'bonuses')"),{'payload':payload})
   except DBAPIError:pass
   else:raise AssertionError('Malformed projection accepted')
  await s.rollback()
 print(json.dumps({'protected_OLD_NEW_bonus_rollup_fixture':'passed','delete_protection':'passed','malformed_journals':'rejected'}),flush=True)
 await engine.dispose()
asyncio.run(main())
