-- 0051 - Keep Champions League qualifying rounds below the league phase.

BEGIN;

INSERT INTO competition_stages (competition_id, stage, stage_factor)
SELECT id, 'regular', 1.05::numeric
FROM competitions
WHERE name = 'Champions League'
ON CONFLICT (competition_id, stage) DO UPDATE
SET stage_factor = EXCLUDED.stage_factor;

COMMIT;
