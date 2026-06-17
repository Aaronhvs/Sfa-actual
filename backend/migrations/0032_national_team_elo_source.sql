-- 0032 - Allow national-team ELO seeds in team_strengths.source
-- Forward:
ALTER TABLE team_strengths
    DROP CONSTRAINT IF EXISTS ck_team_strength_source;

ALTER TABLE team_strengths
    ADD CONSTRAINT ck_team_strength_source
    CHECK (source IN (
        'calculated',
        'default',
        'override',
        'clubelo_seed',
        'elo_v1',
        'national_elo_seed'
    ));

-- Rollback:
-- DELETE FROM team_strengths WHERE source = 'national_elo_seed';
-- ALTER TABLE team_strengths DROP CONSTRAINT IF EXISTS ck_team_strength_source;
-- ALTER TABLE team_strengths
--     ADD CONSTRAINT ck_team_strength_source
--     CHECK (source IN ('calculated', 'default', 'override', 'clubelo_seed', 'elo_v1'));
