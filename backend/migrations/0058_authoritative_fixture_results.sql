-- Additive and idempotent; ordinary goals never include a penalty shootout.
ALTER TABLE fixtures ADD COLUMN IF NOT EXISTS home_penalty_goals SMALLINT;
ALTER TABLE fixtures ADD COLUMN IF NOT EXISTS away_penalty_goals SMALLINT;
ALTER TABLE fixtures ADD COLUMN IF NOT EXISTS result_provenance JSONB;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_fixture_penalty_pair') THEN
  ALTER TABLE fixtures ADD CONSTRAINT ck_fixture_penalty_pair CHECK (
   (home_penalty_goals IS NULL AND away_penalty_goals IS NULL) OR
   (home_penalty_goals IS NOT NULL AND away_penalty_goals IS NOT NULL
    AND home_penalty_goals>=0 AND away_penalty_goals>=0));
 END IF;
END $$;
