-- 0041 - Soften team-strength sensitivity for M1.
--
-- Context:
-- World Cup national-team ELO maps to team_strengths.strength on a 0-100 scale.
-- A top-vs-top national-team match such as France vs Morocco was producing a
-- very large M1 swing because the active config used m1_strength_divisor=100.
-- Raising the divisor to 200 keeps rival quality relevant without treating
-- rank-adjacent elite teams as completely different tiers.
--
-- Forward:
--   active scoring config: M1 = 1 + strength_delta / 200
--
-- Rollback:
-- UPDATE scoring_rules_versions
-- SET config_json = jsonb_set(config_json, '{m1_strength_divisor}', '100'::jsonb, true)
-- WHERE is_active IS TRUE;

UPDATE scoring_rules_versions
SET config_json = jsonb_set(config_json, '{m1_strength_divisor}', '200'::jsonb, true)
WHERE is_active IS TRUE;
