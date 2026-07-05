-- Seed World Cup knockout stage factors for M2.
-- Fixtures store normalized stages from APIFootballProvider.get_stage().
-- Keep this idempotent so production can re-run it safely.

INSERT INTO competition_stages (competition_id, stage, stage_factor)
SELECT c.id, v.stage, v.stage_factor
FROM competitions c
CROSS JOIN (
    VALUES
        ('group', 1.00::numeric),
        ('regular', 1.00::numeric),
        ('round_of_32', 1.10::numeric),
        ('round_of_16', 1.20::numeric),
        ('quarter', 1.35::numeric),
        ('quarter_final', 1.35::numeric),
        ('semi', 1.55::numeric),
        ('semi_final', 1.55::numeric),
        ('third_place', 1.30::numeric),
        ('final', 1.80::numeric)
) AS v(stage, stage_factor)
WHERE c.name = 'World Cup'
ON CONFLICT ON CONSTRAINT uq_competition_stage
DO UPDATE SET stage_factor = EXCLUDED.stage_factor;
