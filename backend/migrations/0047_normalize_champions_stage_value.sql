-- 0047 - Normalize Champions League stage value across M2 and achievements.

BEGIN;

WITH champions AS (
    SELECT id
    FROM competitions
    WHERE name = 'Champions League'
), stage_values(stage, stage_factor) AS (
    VALUES
        ('group', 1.15::numeric),
        ('round_of_16', 1.30::numeric),
        ('quarter', 1.45::numeric),
        ('semi', 1.65::numeric),
        ('final', 1.90::numeric)
)
INSERT INTO competition_stages (competition_id, stage, stage_factor)
SELECT champions.id, stage_values.stage, stage_values.stage_factor
FROM champions
CROSS JOIN stage_values
ON CONFLICT (competition_id, stage) DO UPDATE
SET stage_factor = EXCLUDED.stage_factor;

UPDATE scoring_rules_versions
SET config_json = jsonb_set(
    config_json,
    '{achievement_phase_bonuses,champions_league}',
    '{
        "qualify_ko": 1000,
        "round_of_16": 2000,
        "quarter_final": 3500,
        "semi_final": 6500,
        "runner_up": 11000,
        "winner": 15000
    }'::jsonb,
    true
)
WHERE id = 4;

COMMIT;
