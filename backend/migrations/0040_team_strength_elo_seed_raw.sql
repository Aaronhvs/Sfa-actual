-- 0040 - Preserve ELO seed baselines and allow progressive national-team ELO.
--
-- Forward:
-- 1. Add team_strengths.elo_seed_raw for immutable seed baselines.
-- 2. Backfill existing seed rows so recalculation can start from a stable baseline.
-- 3. Allow national_elo_v1 as the progressive post-ingestion ELO source.
--
-- Rollback notes:
-- DELETE FROM team_strengths WHERE source = 'national_elo_v1';
-- ALTER TABLE team_strengths DROP CONSTRAINT IF EXISTS ck_team_strength_source;
-- ALTER TABLE team_strengths
--     ADD CONSTRAINT ck_team_strength_source CHECK (
--         source IN (
--             'calculated',
--             'default',
--             'override',
--             'clubelo_seed',
--             'elo_v1',
--             'national_elo_seed'
--         )
--     );
-- ALTER TABLE team_strengths DROP COLUMN IF EXISTS elo_seed_raw;

ALTER TABLE team_strengths
    ADD COLUMN IF NOT EXISTS elo_seed_raw NUMERIC(7, 2);

UPDATE team_strengths
SET elo_seed_raw = elo_raw
WHERE elo_seed_raw IS NULL
  AND elo_raw IS NOT NULL
  AND source IN ('clubelo_seed', 'national_elo_seed');

ALTER TABLE team_strengths DROP CONSTRAINT IF EXISTS ck_team_strength_source;

ALTER TABLE team_strengths
    ADD CONSTRAINT ck_team_strength_source CHECK (
        source IN (
            'calculated',
            'default',
            'override',
            'clubelo_seed',
            'elo_v1',
            'national_elo_seed',
            'national_elo_v1'
        )
    );
