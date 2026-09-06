-- Normalize the single-match UEFA Super Cup final with the other supercups.
INSERT INTO competition_stages (competition_id, stage, stage_factor)
SELECT id, 'final', 1.30::numeric
FROM competitions
WHERE name = 'UEFA Super Cup'
ON CONFLICT (competition_id, stage)
DO UPDATE SET stage_factor = EXCLUDED.stage_factor;
