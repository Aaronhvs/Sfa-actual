-- 0049 - Structured provenance for authoritative club ELO seeds.

ALTER TABLE team_elo_seeds
    ADD COLUMN IF NOT EXISTS provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_team_elo_seed_provenance_object'
    ) THEN
        ALTER TABLE team_elo_seeds
            ADD CONSTRAINT ck_team_elo_seed_provenance_object
            CHECK (jsonb_typeof(provenance_json) = 'object');
    END IF;
END $$;

-- Rollback:
-- ALTER TABLE team_elo_seeds DROP CONSTRAINT IF EXISTS ck_team_elo_seed_provenance_object;
-- ALTER TABLE team_elo_seeds DROP COLUMN IF EXISTS provenance_json;
